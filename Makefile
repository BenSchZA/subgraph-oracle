# Install Python virtual environment
install:
	python -m venv deployment/.venv
	source deployment/.venv/bin/activate && pip install -r deployment/requirements.txt

# Authenticate Docker to ECR registry
authenticate_docker:
	aws ecr get-login-password --region eu-north-1 --profile infradao | docker login --username AWS --password-stdin 891377045977.dkr.ecr.eu-north-1.amazonaws.com

# Build Docker image
build_docker_image:
	docker build --pull --rm -f "Dockerfile.availability-oracle" -t graphprotocol/subgraph-availability-oracle:latest "."

# Push Docker image to ECR
push_docker_image:
	docker tag graphprotocol/subgraph-availability-oracle:latest 891377045977.dkr.ecr.eu-north-1.amazonaws.com/graphprotocol/subgraph-availability-oracle:latest
	docker push 891377045977.dkr.ecr.eu-north-1.amazonaws.com/graphprotocol/subgraph-availability-oracle:latest

# AWS CloudFormation deployment
deploy_arbitrum_sepolia:
	cd deployment/ && cdk deploy --profile infradao "arbitrum-sepolia"

deploy_arbitrum_one:
	cd deployment/ && cdk deploy --profile infradao "arbitrum-one"

deploy_monitoring:
	cd deployment/ && cdk deploy --profile infradao "monitoring"

deploy_all:
	cd deployment/ && cdk deploy --profile infradao --all

# cdk bootstrap --profile infradao
# cdk synth --profile infradao
# cdk deploy --profile infradao

# Create certificate
create_certificate:
	openssl req -x509 -newkey rsa:2048 -keyout deployment/certificates/key.pem -out deployment/certificates/cert.pem -days 365 -nodes
