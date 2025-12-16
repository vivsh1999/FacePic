variable "aws_region" {
  description = "AWS Region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "facepic"
}

variable "cloudflare_api_token" {
  description = "Cloudflare API Token"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name (e.g., example.com)"
  type        = string
}

variable "subdomain" {
  description = "Subdomain (e.g., app)"
  type        = string
  default     = "app"
}

variable "mongodb_url" {
  description = "MongoDB Connection String (Atlas)"
  type        = string
  sensitive   = true
}

variable "image_tag" {
  description = "Tag of the Docker image to deploy"
  type        = string
  default     = "latest"
}

# --- GCP Variables ---
variable "gcp_project_id" {
  description = "GCP Project ID for Cloud Run deployment"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region for Cloud Run deployment (e.g., us-central1)"
  type        = string
  default     = "us-central1"
}
