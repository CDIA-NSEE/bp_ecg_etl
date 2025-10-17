#!/usr/bin/env python3
"""Benchmark Setup - Cria 700 cópias de PDF e faz upload para LocalStack S3."""

import os
import shutil
import time
from pathlib import Path

import boto3
from botocore.config import Config


# Configuração LocalStack
LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "raw-pdfs")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "anon-pdfs")

# Benchmark config
SOURCE_PDF = "test_data_local/exemplo_13.pdf"  # PDF base
NUM_COPIES = 700
TEMP_DIR = "benchmark_pdfs"


def create_s3_client():
    """Cria cliente S3 para LocalStack."""
    return boto3.client(
        "s3",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def setup_buckets(s3_client):
    """Cria buckets se não existirem."""
    print("Configurando buckets...")

    for bucket in [INPUT_BUCKET, OUTPUT_BUCKET]:
        try:
            s3_client.head_bucket(Bucket=bucket)
            print(f"  - Bucket {bucket} já existe")
        except:
            s3_client.create_bucket(Bucket=bucket)
            print(f"  - Bucket {bucket} criado")


def clear_bucket(s3_client, bucket):
    """Limpa todos os objetos de um bucket."""
    print(f"Limpando bucket {bucket}...")

    try:
        response = s3_client.list_objects_v2(Bucket=bucket)

        if "Contents" in response:
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
            s3_client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            print(f"  - Removidos {len(objects)} objetos")
        else:
            print(f"  - Bucket já estava vazio")
    except Exception as e:
        print(f"  AVISO: Erro ao limpar bucket: {e}")


def generate_and_upload_pdfs(s3_client):
    """Gera 700 cópias do PDF e faz upload."""
    source_path = Path(SOURCE_PDF)

    if not source_path.exists():
        print(f"ERRO: PDF fonte não encontrado: {SOURCE_PDF}")
        print("   PDFs disponíveis:")
        for pdf in Path("test_data").glob("*.pdf"):
            print(f"   - {pdf}")
        return False

    print(f"PDF fonte: {source_path} ({source_path.stat().st_size / 1024:.1f} KB)")
    print(f"Gerando e fazendo upload de {NUM_COPIES} cópias...")

    start_time = time.time()

    # Ler PDF uma vez
    with open(source_path, "rb") as f:
        pdf_content = f.read()

    # Upload das cópias
    for i in range(1, NUM_COPIES + 1):
        key = f"batch_test/ecg_{i:04d}.pdf"

        s3_client.put_object(
            Bucket=INPUT_BUCKET,
            Key=key,
            Body=pdf_content,
            ContentType="application/pdf",
        )

        if i % 100 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            print(f"  - {i}/{NUM_COPIES} PDFs ({rate:.1f} PDFs/sec)")

    total_time = time.time() - start_time
    total_size_mb = (len(pdf_content) * NUM_COPIES) / (1024 * 1024)

    print(f"\nUpload completo!")
    print(f"   Tempo: {total_time:.2f}s")
    print(f"   Rate: {NUM_COPIES / total_time:.1f} PDFs/sec")
    print(f"   Total: {total_size_mb:.1f} MB")

    return True


def verify_setup(s3_client):
    """Verifica que tudo está pronto para o benchmark."""
    print("\nVerificando setup...")

    # Contar objetos no input bucket
    response = s3_client.list_objects_v2(Bucket=INPUT_BUCKET, Prefix="batch_test/")
    count = response.get("KeyCount", 0)

    print(f"  - {count} PDFs no bucket {INPUT_BUCKET}")

    # Verificar output bucket vazio
    response = s3_client.list_objects_v2(Bucket=OUTPUT_BUCKET)
    out_count = response.get("KeyCount", 0)
    print(f"  - {out_count} objetos no bucket {OUTPUT_BUCKET}")

    if count == NUM_COPIES:
        print(f"\nSetup completo! Pronto para benchmark.")
        return True
    else:
        print(f"\nAVISO: Esperado {NUM_COPIES} PDFs, encontrado {count}")
        return False


def main():
    """Main setup function."""
    print("=" * 60)
    print("BP-ECG ETL - Benchmark Setup")
    print("=" * 60)

    # Criar cliente S3
    s3 = create_s3_client()

    # Setup buckets
    setup_buckets(s3)

    # Limpar buckets
    clear_bucket(s3, INPUT_BUCKET)
    clear_bucket(s3, OUTPUT_BUCKET)

    # Gerar e fazer upload dos PDFs
    if not generate_and_upload_pdfs(s3):
        return 1

    # Verificar setup
    if not verify_setup(s3):
        return 1

    print("\n" + "=" * 60)
    print("Proximo passo: Execute o benchmark")
    print("   ./scripts/benchmark_run.sh")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
