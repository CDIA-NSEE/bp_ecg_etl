"""
Script simplificado para preparar lotes e fazer deploy com Step Functions.

Uso:
    python scripts/prepare_and_deploy.py --bucket bp-ecg-input --batch-size 1000
"""

import argparse
import json
import sys

import boto3


def list_pdfs(bucket: str, prefix: str = "") -> list[str]:
    """Lista todos os PDFs no bucket S3."""
    print(f"Listando PDFs em s3://{bucket}/{prefix}...")

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    pdf_keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" not in page:
            continue
        for obj in page["Contents"]:
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                pdf_keys.append(key)

    print(f"Encontrados {len(pdf_keys):,} PDFs")
    return pdf_keys


def create_batches(keys: list[str], batch_size: int) -> list[dict]:
    """Divide arquivos em lotes."""
    batches = []
    for i in range(0, len(keys), batch_size):
        batch = keys[i : i + batch_size]
        batches.append({"keys": batch})

    print(f"Criados {len(batches)} lotes de até {batch_size} arquivos")
    return batches


def start_step_function(state_machine_arn: str, batches: list[dict]) -> str:
    """Inicia execução da Step Function."""
    sfn = boto3.client("stepfunctions")

    from datetime import datetime

    execution_name = f"bp-ecg-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    payload = {"batches": batches}

    print(f"\nIniciando Step Function...")
    print(f"  State Machine: {state_machine_arn}")
    print(f"  Total de lotes: {len(batches)}")
    print(f"  Total de arquivos: {sum(len(b['keys']) for b in batches):,}")

    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(payload),
    )

    return response["executionArn"]


def main():
    parser = argparse.ArgumentParser(description="Preparar e iniciar processamento paralelo")
    parser.add_argument("--bucket", required=True, help="Bucket S3 de entrada")
    parser.add_argument("--prefix", default="", help="Prefixo S3 (opcional)")
    parser.add_argument(
        "--batch-size", type=int, default=200, help="Arquivos por lote (recomendado: 200)"
    )
    parser.add_argument(
        "--state-machine-arn", help="ARN da State Machine (ou configure AWS_STATE_MACHINE_ARN)"
    )
    parser.add_argument("--region", default="us-east-1", help="Região AWS")

    args = parser.parse_args()

    # Obter ARN da State Machine do CloudFormation
    print("\n[1/4] Verificando State Machine...")

    state_machine_arn = args.state_machine_arn

    if not state_machine_arn:
        try:
            cfn = boto3.client("cloudformation", region_name=args.region)
            response = cfn.describe_stacks(StackName="bp-ecg-etl-stack")
            outputs = response["Stacks"][0]["Outputs"]

            for output in outputs:
                if output["OutputKey"] == "StateMachineArn":
                    state_machine_arn = output["OutputValue"]
                    print(f"  ✓ State Machine encontrada")
                    break

            if not state_machine_arn:
                print("\nERRO: State Machine não encontrada no stack")
                print("Execute primeiro: sam build && sam deploy")
                sys.exit(1)

        except Exception as e:
            print(f"\nERRO: Stack 'bp-ecg-etl-stack' não encontrado")
            print("Execute primeiro: sam build && sam deploy")
            print(f"Detalhes: {e}")
            sys.exit(1)

    try:
        # 1. Listar PDFs
        pdf_keys = list_pdfs(args.bucket, args.prefix)

        if not pdf_keys:
            print("Nenhum PDF encontrado")
            sys.exit(0)

        # 2. Criar lotes
        batches = create_batches(pdf_keys, args.batch_size)

        # 3. Iniciar Step Function
        execution_arn = start_step_function(state_machine_arn, batches)

        # 4. Sucesso
        print("\n" + "=" * 70)
        print("PROCESSAMENTO INICIADO COM SUCESSO")
        print("=" * 70)
        print(f"Execution ARN: {execution_arn}")
        print(f"\nMonitore em: https://console.aws.amazon.com/states/")
        print("=" * 70)

    except Exception as e:
        print(f"\nERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
