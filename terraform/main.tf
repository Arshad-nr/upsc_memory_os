# ─────────────────────────────────────────────────────────────────
# UPSC Memory OS — Terraform Configuration
# ─────────────────────────────────────────────────────────────────
# Provisions: VPC, ALB, ECS Fargate, ECR, Secrets Manager, IAM, CloudWatch
#
# Usage:
#   cd terraform
#   terraform init
#   terraform plan
#   terraform apply
# ─────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
