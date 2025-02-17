import boto3

def ensure_dynamodb_table(table_name):
    dynamodb = boto3.client("dynamodb")

    try:
        dynamodb.describe_table(TableName=table_name)
        print(f"Table '{table_name}' already exists.")
        return
    except dynamodb.exceptions.ResourceNotFoundException:
        print(f"Table '{table_name}' not found. Creating...")

    response = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "s3_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "s3_key", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    )

    print("Table creation initiated:", response)

ensure_dynamodb_table("PDFExtractedData")
