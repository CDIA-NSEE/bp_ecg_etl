# BP-ECG ETL - Sistema de Anonimização de PDFs

🏥 **Sistema de anonimização automática de PDFs de ECG para o projeto BP-ECG**

Este sistema processa PDFs de exames de ECG removendo informações pessoais sensíveis (nome, CPF, RG, CRM) enquanto preserva dados clínicos essenciais (sexo, data/hora do exame, resultados médicos).

## ✨ Funcionalidades

- 🔒 **Anonimização Seletiva**: Remove apenas dados pessoais, preserva informações clínicas
- 📄 **Processamento Inteligente**: Lógica diferenciada para PDFs de 1 página vs 2+ páginas
- 🏷️ **Nomes Únicos**: Geração de nomes únicos usando ULID para evitar conflitos
- ☁️ **Integração S3**: Processamento automático via buckets S3
- ⚡ **AWS Lambda**: Deploy como função serverless
- 📊 **Logging Estruturado**: Monitoramento completo com structlog
- 🐳 **LocalStack**: Teste local completo

## 🚀 Deploy Rápido

### Pré-requisitos

```bash
# Instalar dependências
sudo apt install python3-pip python3-venv
pip install uv

# Instalar AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Iniciar LocalStack
docker-compose up -d
```

### Deploy da Função Lambda

```bash
# Deploy simples e rápido
./deploy_simple.sh

# OU deploy completo com configurações avançadas
python deploy_to_localstack.py
```

## 🧪 Como Testar

### 1. Configurar Credenciais LocalStack

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

### 2. Fazer Upload de PDF

```bash
# Enviar PDF para processamento
aws s3 cp "exemplo.pdf" s3://raw-pdfs/ --endpoint-url http://localhost:4566
```

### 3. Verificar Resultado

```bash
# Listar PDFs anonimizados
aws s3 ls s3://anon-pdfs/ --endpoint-url http://localhost:4566

# Baixar PDF anonimizado
aws s3 cp s3://anon-pdfs/anonymized_XXXXX.pdf . --endpoint-url http://localhost:4566
```

### 4. Teste Automatizado

```bash
# Executar script de teste
python test_function.py
```

## 📁 Estrutura do Projeto

```
bp_ecg_etl/
├── 📦 bp_ecg_etl/                 # Código principal
│   ├── __init__.py
│   ├── main.py                    # Ponto de entrada
│   ├── lambda_main.py             # Handler Lambda
│   ├── config.py                  # Configurações
│   ├── pdf_anonymizer.py          # Lógica de anonimização
│   └── s3_utils.py               # Utilitários S3
├── 🚀 deploy_simple.sh            # Script de deploy rápido
├── 🐍 deploy_to_localstack.py     # Script de deploy completo
├── 🧪 test_function.py            # Script de teste
├── 📋 requirements.txt            # Dependências completas
├── 📦 requirements-lambda.txt     # Dependências otimizadas
├── 🐳 docker-compose.yml          # LocalStack
└── 📖 README.md                   # Esta documentação
```

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `INPUT_BUCKET` | Bucket S3 de entrada | `raw-pdfs` |
| `OUTPUT_BUCKET` | Bucket S3 de saída | `anon-pdfs` |
| `AWS_REGION` | Região AWS | `us-east-1` |
| `DPI_PAGE2_RENDER` | DPI para página 2 | `150` |
| `LINE_TOLERANCE` | Tolerância de linha | `3` |
| `PREVLINE_TOLERANCE` | Tolerância linha anterior | `10` |
| `PADDING` | Padding para redação | `2` |

### Configuração Lambda

- **Runtime**: Python 3.9
- **Memory**: 1024MB
- **Timeout**: 300s (5 minutos)
- **Handler**: `bp_ecg_etl.lambda_main.lambda_handler`

## 🔧 Desenvolvimento

### Setup do Ambiente

```bash
# Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
uv pip install -r requirements.txt
```

### Teste Local

```bash
# Teste de função específica
python -c "from bp_ecg_etl.main import process_pdf_local; process_pdf_local('input.pdf', 'output.pdf')"
```

## 📊 Monitoramento

### Logs do CloudWatch (LocalStack Pro)

```bash
# Visualizar logs em tempo real
aws logs tail /aws/lambda/bp-ecg-etl-anonymizer --endpoint-url http://localhost:4566 --follow
```

### Métricas de Processamento

A função Lambda retorna métricas detalhadas:

```json
{
  "statusCode": 200,
  "body": {
    "message": "PDF processing completed",
    "summary": {
      "total_files": 1,
      "successful": 1,
      "failed": 0
    },
    "results": [{
      "status": "success",
      "input_bucket": "raw-pdfs",
      "input_key": "exemplo.pdf",
      "output_bucket": "anon-pdfs",
      "output_key": "anonymized_01K2H0W0JN0AZCBKTYSE3P5N1B.pdf",
      "processing_time": 0.246,
      "input_size": 188185,
      "output_size": 217058
    }]
  }
}
```

## 🛡️ Segurança e Privacidade

### Dados Removidos
- ✅ Nome do paciente
- ✅ CPF
- ✅ RG
- ✅ CRM do médico
- ✅ Nome do médico

### Dados Preservados
- ✅ Sexo do paciente
- ✅ Data do exame
- ✅ Hora do exame
- ✅ Resultados e interpretações médicas
- ✅ Gráficos e ondas do ECG

## 🐛 Solução de Problemas

### Erro: "ResourceConflictException"
```bash
# Aguardar conclusão da atualização anterior
sleep 15 && ./deploy_simple.sh
```

### Erro: "No such file or directory"
```bash
# Verificar se LocalStack está rodando
docker-compose ps

# Reiniciar se necessário
docker-compose restart
```

### Logs não aparecem
```bash
# LocalStack Community não suporta CloudWatch Logs
# Use LocalStack Pro ou monitore via métricas da função
```

## 📈 Performance

- **PDF 1 página**: ~0.2s
- **PDF 2+ páginas**: ~0.5s
- **Throughput**: ~200 PDFs/minuto
- **Memory usage**: ~200MB por PDF

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.

---

**🏥 BP-ECG ETL** - Anonimização segura e eficiente de PDFs médicos
