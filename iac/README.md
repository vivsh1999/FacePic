# Infrastructure as Code (IaC) - AWS Fargate + S3/CloudFront

This directory contains Terraform configuration to deploy the FacePic application using a production-grade architecture.

## Architecture
- **Frontend**: AWS S3 (Static Hosting) + CloudFront (CDN)
- **Backend**: AWS ECS Fargate (Serverless containers) + ALB
- **DNS**: Cloudflare (pointing to CloudFront)
- **Database**: MongoDB Atlas (External)

## Prerequisites
1.  [Terraform](https://developer.hashicorp.com/terraform/install) installed.
2.  [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured (`aws configure`).
3.  [Docker](https://docs.docker.com/get-docker/) installed.
4.  A Cloudflare account and API Token with `Zone:DNS:Edit` permissions.
5.  A MongoDB Atlas cluster connection string.

## Setup & Deployment

### 1. Configure Variables
Navigate to the terraform directory:
```bash
cd terraform
```

Create a `terraform.tfvars` file from the example:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and fill in your details:
- `cloudflare_api_token`: Your Cloudflare API Token.
- `domain_name`: Your domain (e.g., `example.com`).
- `subdomain`: Subdomain for the app (e.g., `facepic`).
- `mongodb_url`: Your MongoDB Atlas connection string.

### 2. Provision Infrastructure
Initialize and apply the Terraform configuration:
```bash
terraform init
terraform apply
```
Type `yes` to confirm. This may take 15-20 minutes (CloudFront distribution creation is slow).

### 3. Deploy Backend
After Terraform completes, build and push the backend image.

**Authenticate Docker to ECR:**
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
```

**Build and Push:**
```bash
# Build (ensure linux/amd64 platform)
docker build --platform linux/amd64 -t facepic-backend ../../backend

# Tag (Replace <BACKEND_REPO_URL> with the output from terraform)
docker tag facepic-backend:latest <BACKEND_REPO_URL>:latest

# Push
docker push <BACKEND_REPO_URL>:latest

# Update Service
aws ecs update-service --cluster facepic-cluster --service facepic-backend --force-new-deployment
```

### 4. Deploy Frontend
Build the React app and sync it to the S3 bucket.

**Build:**
```bash
cd ../../frontend
npm ci
npm run build
```

**Sync to S3:**
```bash
# Replace <S3_BUCKET_NAME> with the output from terraform
aws s3 sync dist/ s3://<S3_BUCKET_NAME> --delete
```

**Invalidate CloudFront Cache (Optional but recommended):**
```bash
# Replace <DISTRIBUTION_ID> with the output from terraform
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

## Outputs
- `app_url`: The URL where your application is accessible.
- `cloudfront_domain_name`: The raw CloudFront domain.
- `s3_bucket_name`: The S3 bucket where frontend files are stored.
- `ecr_backend_repo`: URL for the backend ECR repository.

## GitHub Actions (CI/CD)

Two workflows have been created in `.github/workflows/` to automate deployments:
1.  **Backend Deploy**: Builds and pushes the Docker image to ECR, then updates the ECS service.
2.  **Frontend Deploy**: Builds the React app, syncs to S3, and invalidates CloudFront.

### Required Secrets
Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions -> New repository secret.

Add the following secrets:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `AWS_ACCESS_KEY_ID` | AWS Access Key | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Key | `wJalr...` |
| `ECR_REPOSITORY_BACKEND` | Name of the Backend ECR Repo | `facepic-backend` |
| `S3_BUCKET_NAME` | Name of the Frontend S3 Bucket | `facepic-frontend-a1b2c3d4` |
| `CLOUDFRONT_DISTRIBUTION_ID` | ID of the CloudFront Distribution | `E1XXXXXX` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API Token | `...` |
| `MONGODB_URL` | MongoDB Connection String | `mongodb+srv://...` |
| `DOMAIN_NAME` | Your Domain | `example.com` |
| `SUBDOMAIN` | Your Subdomain | `facepic` |

### Remote State Setup (Required for CI/CD)
Since GitHub Actions runs Terraform, it needs a shared place to store the state file.
1.  Create an S3 Bucket (e.g., `facepic-terraform-state`).
2.  Create a DynamoDB Table (e.g., `facepic-terraform-locks`) with Partition Key `LockID`.
3.  Edit `iac/terraform/backend.tf` and uncomment the configuration, filling in your bucket/table names.
4.  Commit and push the changes.
