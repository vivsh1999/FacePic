# --- Cloud Run Service (Backend) ---
resource "google_cloud_run_service" "backend" {
  name     = "${var.project_name}-backend"
  location = var.gcp_region

  template {
    spec {
      containers {
        image = "ghcr.io/${var.project_name}/facepic-backend:${var.image_tag}"
        env {
          name  = "MONGODB_URL"
          value = var.mongodb_url
        }
        env {
          name  = "MONGODB_DATABASE"
          value = "imagetag"
        }
        env {
          name  = "CORS_ORIGINS"
          value = "https://${var.subdomain}.${var.domain_name}"
        }
        ports {
          container_port = 8000
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true
}

# Allow unauthenticated invocations
resource "google_cloud_run_service_iam_member" "noauth" {
  location        = google_cloud_run_service.backend.location
  project         = var.gcp_project_id
  service         = google_cloud_run_service.backend.name
  role            = "roles/run.invoker"
  member          = "allUsers"
}

# --- Google Cloud Provider (for Cloud Run) ---
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

