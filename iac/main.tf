# --- Cloudflare Provider ---
provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
# --- TEMP: AWS Provider for Resource Cleanup ---
provider "aws" {
  region = var.aws_region
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
# --- Cloudflare DNS for Pages Custom Domain ---
data "cloudflare_zone" "domain" {
  name = var.domain_name
}

resource "cloudflare_record" "pages_custom_domain" {
  zone_id = data.cloudflare_zone.domain.id
  name    = "facepic"
  type    = "CNAME"
  content = "facepic-frontend.pages.dev"
  proxied = true
}

# --- Cloudflare R2 Bucket ---
resource "cloudflare_r2_bucket" "facepic_images" {
  account_id = var.cloudflare_account_id
  name       = "facepic"
  location   = "ENAM"
}


