"""PDF processing utilities with image extraction."""

import asyncio
import io
import time
from typing import List, Optional
from pathlib import Path

import fitz
from PIL import Image
import structlog

from ..types import S3Client, CropRegion, ProcessingResult, ProcessingStatus, Logger
from .s3_client import download_from_s3, upload_to_s3

logger: Logger = structlog.get_logger(__name__)


async def extract_text_from_pdf(pdf_data: bytes, file_id: str) -> Optional[str]:
    """Extract text from the first page of a PDF.
    
    Args:
        pdf_data: PDF file content as bytes
        file_id: Identifier for the PDF file
        
    Returns:
        Extracted text or None if no text found
        
    Raises:
        Exception: If PDF processing fails
    """
    try:
        logger.info("Extracting text from PDF", file_id=file_id)
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        if len(doc) == 0:
            logger.warning("PDF has no pages", file_id=file_id)
            return None
            
        # Extract text from first page
        page = doc[0]
        text = page.get_text().strip()
        doc.close()
        
        if text:
            logger.info("Successfully extracted text", file_id=file_id, text_length=len(text))
            return text
        else:
            logger.info("No text found in PDF", file_id=file_id)
            return None
            
    except Exception as e:
        logger.error("Failed to extract text from PDF", file_id=file_id, error=str(e))
        raise


async def extract_images_from_pdf(
    s3_client: S3Client,
    pdf_data: bytes,
    file_id: str,
    crop_regions: List[CropRegion],
    dest_bucket: str
) -> List[str]:
    """Extract cropped images from the second page of a PDF.
    
    Args:
        s3_client: Async S3 client
        pdf_data: PDF file content as bytes
        file_id: Identifier for the PDF file
        crop_regions: List of regions to crop from the page
        dest_bucket: S3 bucket to upload images to
        
    Returns:
        List of S3 URIs for uploaded images
        
    Raises:
        Exception: If PDF processing fails
    """
    try:
        logger.info("Extracting images from PDF", file_id=file_id, crop_regions_count=len(crop_regions))
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        if len(doc) < 2:
            logger.warning("PDF has less than 2 pages, cannot extract images", file_id=file_id)
            return []
            
        # Get second page for image extraction
        page = doc[1]
        
        # Convert page to image
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        
        # Open with PIL for cropping
        image = Image.open(io.BytesIO(img_data))
        
        uploaded_uris = []
        
        # Process each crop region
        for i, crop_region in enumerate(crop_regions):
            try:
                # Convert fitz.Rect to PIL crop box (left, top, right, bottom)
                crop_box = (
                    int(crop_region.x0 * 2),  # Scale by zoom factor
                    int(crop_region.y0 * 2),
                    int(crop_region.x1 * 2),
                    int(crop_region.y1 * 2)
                )
                
                # Crop the image
                cropped_image = image.crop(crop_box)
                
                # Convert to bytes
                img_buffer = io.BytesIO()
                cropped_image.save(img_buffer, format='PNG')
                cropped_data = img_buffer.getvalue()
                
                # Upload to S3
                s3_key = f"images/{file_id}_crop_{i}.png"
                await upload_to_s3(s3_client, dest_bucket, s3_key, cropped_data, "image/png")
                
                s3_uri = f"s3://{dest_bucket}/{s3_key}"
                uploaded_uris.append(s3_uri)
                
                logger.info("Successfully cropped and uploaded image", 
                           file_id=file_id, crop_index=i, s3_uri=s3_uri)
                
            except Exception as e:
                logger.error("Failed to process crop region", 
                           file_id=file_id, crop_index=i, error=str(e))
                continue
        
        doc.close()
        logger.info("Completed image extraction", file_id=file_id, images_count=len(uploaded_uris))
        return uploaded_uris
        
    except Exception as e:
        logger.error("Failed to extract images from PDF", file_id=file_id, error=str(e))
        raise


async def process_single_pdf(
    s3_client: S3Client,
    pdf_key: str,
    source_bucket: str,
    dest_bucket: str,
    crop_regions: List[CropRegion]
) -> ProcessingResult:
    """Process a single PDF: extract text and crop images.
    
    Args:
        s3_client: Async S3 client
        pdf_key: S3 key of the PDF to process
        source_bucket: S3 bucket containing the PDF
        dest_bucket: S3 bucket to upload images to
        crop_regions: List of regions to crop from the page
        
    Returns:
        Processing result with status and extracted data
    """
    start_time = time.time()
    file_id = Path(pdf_key).stem
    
    try:
        logger.info("Starting PDF processing", file_id=file_id, pdf_key=pdf_key)
        
        # Download PDF from S3
        pdf_data = await download_from_s3(s3_client, source_bucket, pdf_key)
        
        # Extract text and images concurrently
        text_task = extract_text_from_pdf(pdf_data, file_id)
        images_task = extract_images_from_pdf(s3_client, pdf_data, file_id, crop_regions, dest_bucket)
        
        text, image_uris = await asyncio.gather(text_task, images_task, return_exceptions=True)
        
        # Handle exceptions from concurrent tasks
        if isinstance(text, Exception):
            logger.error("Text extraction failed", file_id=file_id, error=str(text))
            text = None
            
        if isinstance(image_uris, Exception):
            logger.error("Image extraction failed", file_id=file_id, error=str(image_uris))
            image_uris = []
        
        processing_time = int((time.time() - start_time) * 1000)
        
        result = ProcessingResult(
            file_id=file_id,
            status=ProcessingStatus.SUCCESS,
            text=text,
            images=",".join(image_uris) if image_uris else None,
            processing_time_ms=processing_time
        )
        
        logger.info("Successfully processed PDF", 
                   file_id=file_id, processing_time_ms=processing_time)
        return result
        
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error("Failed to process PDF", file_id=file_id, error=str(e), processing_time_ms=processing_time)
        
        return ProcessingResult(
            file_id=file_id,
            status=ProcessingStatus.ERROR,
            error=str(e),
            processing_time_ms=processing_time
        )
