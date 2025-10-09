#!/bin/bash
# Cria ZIP da Lambda manualmente

set -e

echo "Criando ZIP da Lambda..."

# Limpa diretório temporário
rm -rf build/
mkdir -p build/

# Copia código
cp -r bp_ecg_etl build/

# Instala dependências
pip install -r requirements.txt -t build/ --quiet

# Cria ZIP
cd build
zip -r ../lambda.zip . -q
cd ..

echo "✓ ZIP criado: lambda.zip ($(du -h lambda.zip | cut -f1))"
