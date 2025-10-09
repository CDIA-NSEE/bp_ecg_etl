"""Script para testar processamento de PDF localmente."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bp_ecg_etl.pdf_processor import process_complete_pdf


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_local.py input.pdf [output.pdf]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_name(f"{input_path.stem}_anonimizado.pdf")

    if not input_path.exists():
        print(f"Erro: {input_path} não encontrado")
        sys.exit(1)

    print(f"Processando: {input_path}")
    print("  - Anonimizando página 1...")
    print("  - Extraindo página 2 como PNG (300 DPI)...")
    print("  - Mesclando e comprimindo...")

    # Processar
    pdf_bytes = input_path.read_bytes()
    result = process_complete_pdf(pdf_bytes, dpi=300)

    # Salvar
    output_path.write_bytes(result)

    print(f"\n✓ Concluído: {output_path}")
    print(f"  Tamanho original: {len(pdf_bytes):,} bytes")
    print(f"  Tamanho final: {len(result):,} bytes")


if __name__ == "__main__":
    main()
