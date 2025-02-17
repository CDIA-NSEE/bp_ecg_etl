import boto3
import dask
import awswrangler as wr
import docling
import logging
import time
from dask.distributed import Client, as_completed
from dask.diagnostics import ProgressBar
from typing import List, Optional, Dict

from .types import PDFRecord


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

S3_CLIENT = boto3.client("s3")
DYNAMODB_CLIENT = boto3.client("dynamodb")
BUCKET_NAME = "your-bucket-name"
TABLE_NAME = "your-dynamodb-table"
BATCH_SIZE = 100

def init_dask_client() -> Client:
    """Initialize and return a Dask distributed client."""
    client = Client()
    logging.info("Dask client initialized.")
    return client

def check_or_create_table(table_name: str) -> None:
    """Check if a DynamoDB table exists. If not, create it."""
    try:
        DYNAMODB_CLIENT.describe_table(TableName=table_name)
        logging.info(f"Table '{table_name}' already exists.")
    except DYNAMODB_CLIENT.exceptions.ResourceNotFoundException:
        logging.info(f"Table '{table_name}' does not exist. Creating table...")
        
        DYNAMODB_CLIENT.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )

        while True:
            table_status = DYNAMODB_CLIENT.describe_table(TableName=table_name)["Table"]["TableStatus"]
            if table_status == "ACTIVE":
                break
            logging.info("Waiting for table to become active...")
            time.sleep(2)

        logging.info(f"Table '{table_name}' created successfully.")

def list_s3_pdfs(bucket_name: str) -> List[str]:
    """List all PDFs from an S3 bucket using pagination."""
    paginator = S3_CLIENT.get_paginator("list_objects_v2")
    pdf_keys = []

    for page in paginator.paginate(Bucket=bucket_name, Prefix="pdfs/"):
        pdf_keys.extend(obj["Key"] for obj in page.get("Contents", []) if obj["Key"].endswith(".pdf"))

    logging.info(f"Found {len(pdf_keys)} PDF files in S3.")
    return pdf_keys

def process_pdf(s3_key: str) -> Optional[Dict]:
    """Download and extract text from a PDF using Docling."""
    try:
        obj = S3_CLIENT.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        doc = docling.read_pdf(obj["Body"])
        text = doc.extract_text(limit=1000)
        
        record = PDFRecord(
            name=s3_key.split("/")[-1],
            content=text
        )
        return record.model_dump(by_alias=True)
    except Exception as e:
        logging.error(f"Error processing {s3_key}: {e}")
        return None

def save_batch_to_dynamodb(records: List[Dict], table_name: str) -> None:
    """Save a batch of records to DynamoDB."""
    if records:
        wr.dynamodb.put_items(table_name=table_name, items=records)
        logging.info(f"Saved {len(records)} records to DynamoDB.")

def run_etl() -> None:
    """Main ETL execution pipeline using Dask Futures."""
    client = init_dask_client()
    check_or_create_table(TABLE_NAME)

    pdf_keys = list_s3_pdfs(BUCKET_NAME)
    futures = client.map(process_pdf, pdf_keys)

    batch: List[Dict] = []
    with ProgressBar():
        for future in as_completed(futures):
            result = future.result()
            if result:
                batch.append(result)

            if len(batch) >= BATCH_SIZE:
                save_batch_to_dynamodb(batch, TABLE_NAME)
                batch = []

    if batch:
        save_batch_to_dynamodb(batch, TABLE_NAME)

    logging.info("ETL complete!")

if __name__ == "__main__":
    run_etl()
