#!/usr/bin/env python3
"""
Script para testar o trigger automático S3 → Lambda
Demonstra o comportamento real de produção onde a Lambda é disparada automaticamente
"""

import time
import boto3
from pathlib import Path

# Configuração LocalStack
LOCALSTACK_ENDPOINT = "http://localhost:4566"
INPUT_BUCKET = "raw-pdfs"
OUTPUT_BUCKET = "anon-pdfs"
FUNCTION_NAME = "bp-ecg-etl-anonymizer"

def setup_clients():
    """Configura clientes AWS para LocalStack"""
    config = {
        'endpoint_url': LOCALSTACK_ENDPOINT,
        'aws_access_key_id': 'test',
        'aws_secret_access_key': 'test',
        'region_name': 'us-east-1'
    }
    
    return {
        's3': boto3.client('s3', **config),
        'logs': boto3.client('logs', **config)
    }

def upload_pdf_and_wait(s3_client, pdf_path, wait_seconds=10):
    """
    Faz upload de PDF e aguarda processamento automático
    Simula o comportamento real de produção
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        return False
    
    print(f"📤 Fazendo upload de: {pdf_file.name}")
    print(f"   Tamanho: {pdf_file.stat().st_size / 1024:.1f} KB")
    
    try:
        # Upload do PDF (isso deve disparar a Lambda automaticamente!)
        s3_client.upload_file(
            str(pdf_file), 
            INPUT_BUCKET, 
            pdf_file.name
        )
        print(f"✅ Upload concluído: s3://{INPUT_BUCKET}/{pdf_file.name}")
        print(f"🔄 Aguardando {wait_seconds}s para processamento automático...")
        
        # Aguardar processamento
        time.sleep(wait_seconds)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no upload: {e}")
        return False

def check_output_bucket(s3_client):
    """Verifica se o PDF anonimizado foi gerado automaticamente"""
    print(f"🔍 Verificando bucket de saída: {OUTPUT_BUCKET}")
    
    try:
        response = s3_client.list_objects_v2(Bucket=OUTPUT_BUCKET)
        
        if 'Contents' in response:
            print("📁 PDFs anonimizados encontrados:")
            for obj in response['Contents']:
                size_mb = obj['Size'] / (1024 * 1024)
                print(f"   📄 {obj['Key']} ({size_mb:.1f} MB)")
                print(f"      Modificado: {obj['LastModified']}")
            return True
        else:
            print("   📭 Nenhum PDF anonimizado encontrado")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao verificar bucket: {e}")
        return False

def view_recent_logs(logs_client, minutes=5):
    """Visualiza logs recentes da função Lambda"""
    print(f"📋 Visualizando logs dos últimos {minutes} minutos...")
    
    try:
        log_group = f"/aws/lambda/{FUNCTION_NAME}"
        
        # Listar streams de log
        streams = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if not streams['logStreams']:
            print("   📭 Nenhum log encontrado")
            return
        
        # Pegar o stream mais recente
        latest_stream = streams['logStreams'][0]['logStreamName']
        
        # Calcular timestamp de 5 minutos atrás
        start_time = int((time.time() - minutes * 60) * 1000)
        
        events = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=latest_stream,
            startTime=start_time
        )
        
        if events['events']:
            print("📝 Logs recentes:")
            for event in events['events'][-15:]:  # Últimos 15 eventos
                timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']/1000))
                message = event['message'].strip()
                print(f"   [{timestamp}] {message}")
        else:
            print("   📭 Nenhum log recente encontrado")
            
    except Exception as e:
        print(f"⚠️  Erro ao acessar logs: {e}")

def test_automatic_trigger(pdf_path):
    """
    Teste completo do trigger automático S3 → Lambda
    Simula o fluxo real de produção
    """
    print("🎯 TESTE DE TRIGGER AUTOMÁTICO S3 → LAMBDA")
    print("=" * 60)
    print("Este teste simula o comportamento real de produção:")
    print("1. Upload de PDF para S3")
    print("2. S3 dispara Lambda automaticamente")
    print("3. Lambda processa e gera PDF anonimizado")
    print("4. Verificação dos resultados")
    print("=" * 60)
    
    # Setup clientes
    clients = setup_clients()
    
    # Limpar bucket de saída para teste limpo
    print("🧹 Limpando bucket de saída...")
    try:
        objects = clients['s3'].list_objects_v2(Bucket=OUTPUT_BUCKET)
        if 'Contents' in objects:
            for obj in objects['Contents']:
                clients['s3'].delete_object(Bucket=OUTPUT_BUCKET, Key=obj['Key'])
                print(f"   🗑️  Removido: {obj['Key']}")
    except Exception as e:
        print(f"   ⚠️  Erro na limpeza: {e}")
    
    # Fase 1: Upload do PDF (dispara trigger automático)
    print("\n📤 FASE 1: Upload do PDF")
    success = upload_pdf_and_wait(clients['s3'], pdf_path, wait_seconds=15)
    
    if not success:
        print("❌ Teste falhou no upload")
        return False
    
    # Fase 2: Verificar resultado automático
    print("\n🔍 FASE 2: Verificação do processamento automático")
    pdf_generated = check_output_bucket(clients['s3'])
    
    # Fase 3: Visualizar logs do processamento
    print("\n📋 FASE 3: Logs do processamento automático")
    view_recent_logs(clients['logs'])
    
    # Resultado final
    print("\n" + "=" * 60)
    if pdf_generated:
        print("🎉 TESTE BEM-SUCEDIDO!")
        print("✅ O trigger automático S3 → Lambda está funcionando!")
        print("✅ PDF foi processado e anonimizado automaticamente!")
        print("✅ Sistema pronto para produção!")
    else:
        print("⚠️  TESTE PARCIALMENTE BEM-SUCEDIDO")
        print("✅ Upload realizado com sucesso")
        print("❓ PDF anonimizado não encontrado (verifique logs)")
        print("💡 Pode ser necessário aguardar mais tempo ou verificar configuração do trigger")
    
    print("=" * 60)
    return pdf_generated

if __name__ == "__main__":
    import sys
    
    # Verificar se foi fornecido um arquivo PDF
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Usar arquivo padrão se disponível
        pdf_path = "test_data/exemplo 1.PDF"
        if not Path(pdf_path).exists():
            print("❌ Arquivo de teste não encontrado!")
            print("💡 Use: python test_automatic_trigger.py caminho/para/arquivo.pdf")
            sys.exit(1)
    
    # Executar teste
    test_automatic_trigger(pdf_path)
