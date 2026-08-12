# ── Input Variables ───────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "upsc"
}

variable "environment" {
  description = "Environment (production, staging)"
  type        = string
  default     = "production"
}

# ── Secrets (passed via terraform.tfvars or env vars) ────────────

variable "database_url" {
  description = "Supabase PostgreSQL connection string"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true
}

variable "qdrant_url" {
  description = "Qdrant Cloud cluster URL"
  type        = string
  sensitive   = true
}

variable "qdrant_api_key" {
  description = "Qdrant Cloud API key"
  type        = string
  sensitive   = true
}

variable "backend_cpu" {
  description = "Backend task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Backend task memory in MB"
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "Frontend task CPU units"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Frontend task memory in MB"
  type        = number
  default     = 512
}
