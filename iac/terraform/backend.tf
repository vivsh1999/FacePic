terraform {
  backend "s3" {
    # Replace these with your actual bucket details
    # bucket         = "facepic-terraform-state"
    # key            = "terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "facepic-terraform-locks"
    # encrypt        = true
  }
}
