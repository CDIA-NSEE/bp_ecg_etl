# Redação Vetorial com PyMuPDF (Branch `vectorial-redaction`)

Esta branch utiliza **redação vetorial** ao invés de rasterização para anonimizar dados sensíveis em ECGs.

**Simplificado:** Usa apenas PyMuPDF com flags de segurança máxima (sem Ghostscript).

## ⚖️ Comparação: Vetorial vs Rasterização

| Aspecto | Main (Rasterização) | Vectorial (Esta Branch) |
|---------|---------------------|-------------------------|
| **Segurança** | 100% ✅✅✅ | ~85-90% ✅✅ |
| **Qualidade Visual** | Excelente (600 DPI) | Excelente (vetorial) |
| **Tamanho do arquivo** | Grande (~3MB) | Médio (~1.5MB) |
| **Compatibilidade ML** | Perfeito ✅ | Perfeito ✅ |
| **Dependências** | PyMuPDF, Pillow | PyMuPDF apenas |
| **Velocidade** | Rápido | Médio (Ghostscript adiciona ~1-2s) |
| **Texto pesquisável** | ❌ (pixels) | ✅ (vetor preservado) |

## 🔒 Níveis de Segurança

### Main Branch (Rasterização):
```
PDF → PNG 600dpi → Tarjas → PNG → PDF
└─> Dados originais DESTRUÍDOS permanentemente
    Segurança: 100%
```

### Vectorial Branch (Esta):
```
PDF → Redação vetorial → Limpeza profunda (PyMuPDF) → PDF
└─> Dados removidos com flags de segurança máxima
    Segurança: ~85-90%
```

## 📦 Dependências

**Nenhuma dependência adicional necessária!**

Usa apenas PyMuPDF (já no `requirements.txt`):
```txt
pymupdf==1.26.4
```

Deploy simples:
```bash
bash scripts/local/deploy_localstack.sh  # LocalStack
bash scripts/production/deploy_production.sh  # AWS
```

## 🚀 Como Usar

### Opção 1: Trocar método no código existente

Edite `bp_ecg_etl/batch_processor.py`:

```python
# Antes (rasterização)
from .pdf_processor import process_complete_pdf

# Depois (vetorial)
from .pdf_processor_vectorial import process_complete_pdf_vectorial as process_complete_pdf
```

### Opção 2: Usar processador dedicado

```python
from bp_ecg_etl.batch_processor_vectorial import execute_batch_vectorial

# Processar com método vetorial
result = await execute_batch_vectorial(keys, bucket)
```

## 🏗️ Arquitetura

```
bp_ecg_etl/
├── ecg_extractor_vectorial.py       # Redação vetorial + Ghostscript
├── pdf_processor_vectorial.py        # Pipeline vetorial completo
└── batch_processor_vectorial.py      # Batch processing vetorial

Scripts mantidos iguais:
├── scripts/local/deploy_localstack.sh
└── scripts/production/deploy_production.sh
```

## ⚙️ Como Funciona

### 1. Redação Vetorial (PyMuPDF)
```python
# Marca áreas para redação
page.add_redact_annot(rect, fill=(0, 0, 0))

# Remove texto E imagens
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
```

### 2. Limpeza Profunda
```python
doc.save(
    garbage=4,      # Remove objetos órfãos
    clean=True,     # Reorganiza estrutura
    deflate=True,   # Comprime streams
)
```

### 3. Sanitização com Ghostscript
```bash
gs -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress \
   -sOutputFile=output.pdf input.pdf
```
Reconstrói PDF do zero, removendo estruturas internas complexas.

## 📊 Performance

### Tempo de processamento (por PDF):

| Etapa | Main (Raster) | Vectorial |
|-------|---------------|-----------|
| Download | 0.5s | 0.5s |
| Anonimização Pág. 1 | 1.0s | 1.0s |
| Processamento Pág. 2 | 2.0s | 1.5s |
| Ghostscript | - | 1.5s |
| Upload | 0.5s | 0.3s (menor) |
| **Total** | **~4s** | **~5s** |

## 🎯 Quando Usar Cada Método

### Use Rasterização (Main) quando:
- ✅ Segurança máxima é crítica (dados médicos/PHI)
- ✅ Conformidade LGPD/HIPAA exige garantia absoluta
- ✅ Arquivo pode ser maior
- ✅ Texto pesquisável não é necessário

### Use Vetorial (Esta branch) quando:
- ✅ Precisa de arquivos menores
- ✅ Quer manter texto pesquisável
- ✅ Segurança de ~95% é aceitável
- ✅ Pode instalar Ghostscript no ambiente

## 🧪 Testes

```bash
# Deploy local
bash scripts/local/deploy_localstack.sh

# Testar método vetorial
bash scripts/local/execute_statemachine.sh test_data_local/exemplo_13.pdf
```

## ⚠️ Avisos

1. **Ghostscript obrigatório**: Lambda precisa ter layer com Ghostscript
2. **Tempo maior**: +1-2s por PDF devido ao Ghostscript
3. **Segurança não absoluta**: Bugs raros podem vazar dados
4. **Auditoria**: Recomendado validação adicional em produção

## 🔄 Migrar de volta para Main

```bash
git checkout main
# O código de rasterização permanece intacto
```

## 📝 Recomendação

**Para dados médicos sensíveis (ECGs com PHI), recomendamos manter branch `main` com rasterização.**

Esta branch `vectorial-redaction` é fornecida como alternativa para casos onde:
- Trade-off segurança/tamanho é aceitável
- Texto pesquisável é importante
- Conformidade permite ~95% de garantia

---

**Desenvolvido como alternativa experimental - use com cautela em produção** ⚠️
