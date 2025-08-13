#!/usr/bin/env python3
"""
Script de teste para a função Lambda BP-ECG ETL
Testa o processamento de PDFs no LocalStack
"""

import json
import boto3
from pathlib import Path

# Configuração LocalStack
LOCALSTACK_ENDPOINT = "http://localhost:4566"
FUNCTION_NAME = "bp-ecg-etl-anonymizer"
INPUT_BUCKET = "raw-pdfs"
OUTPUT_BUCKET = "anon-pdfs"

def setup_aws_client():
    """Configura cliente AWS para LocalStack"""
    return boto3.client(
        'lambda',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def setup_s3_client():
    """Configura cliente S3 para LocalStack"""
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def create_test_payload(pdf_filename):
    """Cria payload de teste simulando evento S3"""
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": INPUT_BUCKET},
                    "object": {"key": pdf_filename}
                }
            }
        ]
    }

def test_lambda_function(pdf_filename="exemplo 3.pdf"):
    """Testa a função Lambda com um PDF"""
    print("🚀 Teste da Função Lambda BP-ECG ETL")
    print("=" * 50)
    
    # Setup clientes
    lambda_client = setup_aws_client()
    s3_client = setup_s3_client()
    
    # Criar payload de teste
    payload = create_test_payload(pdf_filename)
    
    try:
        # Invocar função Lambda
        print(f"🧪 Testando função Lambda com arquivo: {pdf_filename}")
        response = lambda_client.invoke(
            FunctionName=FUNCTION_NAME,
            Payload=json.dumps(payload)
        )
        
        # Processar resposta
        status_code = response['StatusCode']
        response_payload = json.loads(response['Payload'].read())
        
        print(f"✅ Status Code: {status_code}")
        print(f"📄 Response: {json.dumps(response_payload, indent=2)}")
        
        # Verificar bucket de saída
        print(f"\n🔍 Verificando bucket de saída ({OUTPUT_BUCKET})...")
        try:
            objects = s3_client.list_objects_v2(Bucket=OUTPUT_BUCKET)
            if 'Contents' in objects:
                print("📁 Arquivos encontrados:")
                for obj in objects['Contents']:
                    size_kb = obj['Size'] / 1024
                    print(f"   📄 {obj['Key']} ({size_kb:.1f} KB)")
            else:
                print("   📭 Nenhum arquivo encontrado")
        except Exception as e:
            print(f"   ❌ Erro ao listar bucket: {e}")
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False
    
    print("=" * 50)
    print("🎉 Teste concluído!")
    return True

def view_logs():
    """Visualiza logs da função Lambda (se disponível)"""
    try:
        logs_client = boto3.client(
            'logs',
            endpoint_url=LOCALSTACK_ENDPOINT,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
        
        log_group = f"/aws/lambda/{FUNCTION_NAME}"
        print(f"📋 Visualizando logs do grupo: {log_group}")
        
        # Listar streams de log
        streams = logs_client.describe_log_streams(logGroupName=log_group)
        
        if streams['logStreams']:
            latest_stream = streams['logStreams'][0]['logStreamName']
            events = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=latest_stream
            )
            
            print("📝 Últimos logs:")
            for event in events['events'][-10:]:  # Últimos 10 eventos
                print(f"   {event['message'].strip()}")
        else:
            print("   📭 Nenhum log encontrado")
            
    except Exception as e:
        print(f"⚠️  Logs não disponíveis: {e}")

if __name__ == "__main__":
    # Executar teste
    success = test_lambda_function()
    
    if success:
        print("\n📋 Deseja visualizar os logs? (LocalStack Pro apenas)")
        view_logs()
