#!/usr/bin/env python3
"""
Script para fazer deploy da função Lambda BP-ECG ETL para LocalStack
"""

import os
import sys
import json
import zipfile
import tempfile
import subprocess
from pathlib import Path

def create_lambda_package():
    """Criar pacote ZIP da função Lambda"""
    print("📦 Criando pacote Lambda...")
    
    # Diretório atual
    project_dir = Path(__file__).parent
    
    # Criar arquivo ZIP temporário
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        zip_path = tmp_file.name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        
        # Adicionar módulo bp_ecg_etl
        bp_ecg_etl_dir = project_dir / 'bp_ecg_etl'
        for py_file in bp_ecg_etl_dir.rglob('*.py'):
            if '__pycache__' not in str(py_file):
                arcname = py_file.relative_to(project_dir)
                zip_file.write(py_file, arcname)
                print(f"   Adicionado: {arcname}")
        
        # Adicionar dependências do requirements.txt
        print("   📚 Instalando dependências...")
        
        # Criar diretório temporário para dependências
        with tempfile.TemporaryDirectory() as deps_dir:
            # Instalar dependências com uv (mais rápido)
            subprocess.run([
                'uv', 'pip', 'install',
                '-r', str(project_dir / 'requirements.txt'),
                '--target', deps_dir,
                '--no-deps'  # Evitar dependências desnecessárias
            ], check=True, capture_output=True)
            
            # Adicionar dependências ao ZIP
            deps_path = Path(deps_dir)
            for item in deps_path.rglob('*'):
                if item.is_file() and '__pycache__' not in str(item):
                    arcname = item.relative_to(deps_path)
                    zip_file.write(item, arcname)
    
    print(f"✅ Pacote criado: {zip_path}")
    return zip_path

def deploy_to_localstack(zip_path: str):
    """Fazer deploy da função para LocalStack"""
    print("🚀 Fazendo deploy para LocalStack...")
    
    # Configurações da função Lambda
    function_name = "bp-ecg-etl-anonymizer"
    handler = "bp_ecg_etl.main.lambda_handler"
    runtime = "python3.9"
    timeout = 300  # 5 minutos
    memory_size = 1024  # 1GB
    
    # Variáveis de ambiente
    environment = {
        "Variables": {
            "INPUT_BUCKET": "raw-pdfs",
            "OUTPUT_BUCKET": "anon-pdfs",
            "AWS_REGION": "us-east-1",
            "DPI_PAGE2_RENDER": "150",
            "LINE_TOLERANCE": "5",
            "PREVLINE_TOLERANCE": "20",
            "PADDING": "2"
        }
    }
    
    # Endpoint do LocalStack
    localstack_endpoint = "http://localhost:4566"
    
    try:
        # Verificar se a função já existe
        print("🔍 Verificando se função já existe...")
        result = subprocess.run([
            'aws', 'lambda', 'get-function',
            '--function-name', function_name,
            '--endpoint-url', localstack_endpoint
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("♻️  Função já existe, atualizando código...")
            # Atualizar código da função
            subprocess.run([
                'aws', 'lambda', 'update-function-code',
                '--function-name', function_name,
                '--zip-file', f'fileb://{zip_path}',
                '--endpoint-url', localstack_endpoint
            ], check=True)
            
            # Atualizar configuração
            subprocess.run([
                'aws', 'lambda', 'update-function-configuration',
                '--function-name', function_name,
                '--timeout', str(timeout),
                '--memory-size', str(memory_size),
                '--environment', json.dumps(environment),
                '--endpoint-url', localstack_endpoint
            ], check=True)
            
        else:
            print("🆕 Criando nova função...")
            # Criar nova função
            subprocess.run([
                'aws', 'lambda', 'create-function',
                '--function-name', function_name,
                '--runtime', runtime,
                '--role', 'arn:aws:iam::000000000000:role/lambda-role',
                '--handler', handler,
                '--zip-file', f'fileb://{zip_path}',
                '--timeout', str(timeout),
                '--memory-size', str(memory_size),
                '--environment', json.dumps(environment),
                '--endpoint-url', localstack_endpoint
            ], check=True)
        
        print("✅ Deploy realizado com sucesso!")
        
        # Mostrar informações da função
        print("\n📋 Informações da função:")
        print(f"   Nome: {function_name}")
        print(f"   Handler: {handler}")
        print(f"   Runtime: {runtime}")
        print(f"   Timeout: {timeout}s")
        print(f"   Memory: {memory_size}MB")
        print(f"   Endpoint: {localstack_endpoint}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro no deploy: {e}")
        return False

def create_s3_buckets():
    """Criar buckets S3 necessários no LocalStack"""
    print("🪣 Criando buckets S3...")
    
    buckets = ["bp-ecg-input", "bp-ecg-output"]
    localstack_endpoint = "http://localhost:4566"
    
    for bucket in buckets:
        try:
            subprocess.run([
                'aws', 's3', 'mb', f's3://{bucket}',
                '--endpoint-url', localstack_endpoint
            ], check=True, capture_output=True)
            print(f"   ✅ Bucket criado: {bucket}")
        except subprocess.CalledProcessError:
            print(f"   ℹ️  Bucket já existe: {bucket}")

def setup_s3_trigger():
    """Configurar trigger S3 para a função Lambda"""
    print("🔗 Configurando trigger S3...")
    
    function_name = "bp-ecg-etl-anonymizer"
    bucket_name = "bp-ecg-input"
    localstack_endpoint = "http://localhost:4566"
    
    # Configuração da notificação S3
    notification_config = {
        "LambdaConfigurations": [
            {
                "Id": "bp-ecg-etl-trigger",
                "LambdaFunctionArn": f"arn:aws:lambda:us-east-1:000000000000:function:{function_name}",
                "Events": ["s3:ObjectCreated:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {
                                "Name": "suffix",
                                "Value": ".pdf"
                            }
                        ]
                    }
                }
            }
        ]
    }
    
    try:
        # Dar permissão para S3 invocar a Lambda
        subprocess.run([
            'aws', 'lambda', 'add-permission',
            '--function-name', function_name,
            '--statement-id', 's3-trigger',
            '--action', 'lambda:InvokeFunction',
            '--principal', 's3.amazonaws.com',
            '--source-arn', f'arn:aws:s3:::{bucket_name}',
            '--endpoint-url', localstack_endpoint
        ], check=True, capture_output=True)
        
        # Configurar notificação no bucket
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(notification_config, tmp_file, indent=2)
            config_file = tmp_file.name
        
        subprocess.run([
            'aws', 's3api', 'put-bucket-notification-configuration',
            '--bucket', bucket_name,
            '--notification-configuration', f'file://{config_file}',
            '--endpoint-url', localstack_endpoint
        ], check=True)
        
        os.unlink(config_file)
        print("✅ Trigger S3 configurado!")
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Erro ao configurar trigger: {e}")

def test_deployment():
    """Testar o deployment fazendo upload de um PDF"""
    print("🧪 Testando deployment...")
    
    # Verificar se existe um PDF de teste
    test_pdf = Path(".test_data/exemplo 3.pdf")
    if not test_pdf.exists():
        print("⚠️  PDF de teste não encontrado, pulando teste automático")
        return
    
    localstack_endpoint = "http://localhost:4566"
    bucket_name = "bp-ecg-input"
    
    try:
        # Fazer upload do PDF de teste
        subprocess.run([
            'aws', 's3', 'cp', str(test_pdf),
            f's3://{bucket_name}/test-{test_pdf.name}',
            '--endpoint-url', localstack_endpoint
        ], check=True)
        
        print(f"✅ PDF de teste enviado: {test_pdf.name}")
        print("   A função Lambda deve ser invocada automaticamente!")
        print(f"   Verifique o bucket de saída: s3://bp-ecg-output")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro no teste: {e}")

def main():
    """Função principal"""
    print("🚀 BP-ECG ETL - Deploy para LocalStack")
    print("=" * 50)
    
    # Verificar se LocalStack está rodando
    try:
        subprocess.run([
            'curl', '-s', 'http://localhost:4566/_localstack/health'
        ], check=True, capture_output=True)
        print("✅ LocalStack está rodando")
    except subprocess.CalledProcessError:
        print("❌ LocalStack não está rodando!")
        print("   Inicie o LocalStack primeiro: docker-compose up -d")
        return False
    
    # Verificar se AWS CLI está configurado
    try:
        subprocess.run(['aws', '--version'], check=True, capture_output=True)
        print("✅ AWS CLI disponível")
    except subprocess.CalledProcessError:
        print("❌ AWS CLI não encontrado!")
        print("   Instale o AWS CLI primeiro")
        return False
    
    # Configurar AWS CLI para LocalStack (se necessário)
    os.environ['AWS_ACCESS_KEY_ID'] = 'test'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    
    try:
        # 1. Criar pacote Lambda
        zip_path = create_lambda_package()
        
        # 2. Criar buckets S3
        create_s3_buckets()
        
        # 3. Fazer deploy da função
        if not deploy_to_localstack(zip_path):
            return False
        
        # 4. Configurar trigger S3
        setup_s3_trigger()
        
        # 5. Testar deployment
        test_deployment()
        
        print("\n🎉 Deploy completo!")
        print("=" * 50)
        print("📋 Próximos passos:")
        print("   1. Faça upload de PDFs para: s3://bp-ecg-input")
        print("   2. Verifique resultados em: s3://bp-ecg-output")
        print("   3. Monitore logs: aws logs tail /aws/lambda/bp-ecg-etl-anonymizer --endpoint-url http://localhost:4566")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante deploy: {e}")
        return False
    
    finally:
        # Limpar arquivo ZIP temporário
        if 'zip_path' in locals():
            try:
                os.unlink(zip_path)
            except:
                pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
