output "app_url" {
  description = "URL of the application"
  value       = "https://${var.subdomain}.${var.domain_name}"
}

output "cloudfront_domain_name" {
  description = "CloudFront Domain Name"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront Distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

output "s3_bucket_name" {
  description = "S3 Bucket Name for Frontend"
  value       = aws_s3_bucket.frontend.id
}

output "ecr_backend_repo" {
  description = "ECR Repository URL for Backend"
  value       = aws_ecr_repository.backend.repository_url
}
