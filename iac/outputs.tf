output "app_url" {
  description = "URL of the application"
  value       = "https://${var.subdomain}.${var.domain_name}"
}

