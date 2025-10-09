# BP-ECG ETL

Processamento paralelo de PDFs de ECG com anonimização.

## Como Usar

### 1. Configurar

Edite `template.yaml` (linhas 17-18):

```yaml
INPUT_BUCKET: "seu-bucket-entrada"
OUTPUT_BUCKET: "seu-bucket-saida"
```

### 2. Deploy (cria State Machine + Lambda)

```bash
sam build
sam deploy --guided
```

Isto cria automaticamente:
- Lambda Processor (10GB RAM)
- Step Functions State Machine (MaxConcurrency: 500)
- IAM Roles necessárias

### 3. Upload PDFs

```bash
aws s3 cp pdfs/ s3://seu-bucket-entrada/ --recursive
```

### 4. Executar

```bash
python scripts/prepare_and_deploy.py --bucket seu-bucket-entrada
```

## Arquitetura

```
Script Local → Step Functions → 500 Lambdas → S3
```

- **Script**: Lista PDFs e divide em lotes de 1000
- **Step Functions**: Controla 500 Lambdas simultâneas
- **Lambda**: Processa 1000 PDFs com 15 workers

## Processamento

Cada PDF:
1. Download do S3
2. Anonimiza página 1 (remove CPF, nome, etc)
3. Extrai página 2 como PNG (300 DPI)
4. Mescla e comprime
5. Upload para S3 de saída

## Performance

- 1.5M arquivos em ~7-8 horas
- 500 Lambdas simultâneas (10GB RAM cada)
- Custo: ~$210 para 1.5M PDFs

## Documentação

Ver `FLUXO.md` para detalhes completos.
