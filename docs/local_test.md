# Build the Lambda function
sam build

# Test locally
sam local invoke BpEcgEtlFunction --event test-event.json

# Deploy to AWS
sam deploy --guided