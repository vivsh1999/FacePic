terraform {
  backend "s3" {
    bucket         = "facepic-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "facepic-terraform-locks"
    encrypt        = true
  }
}
