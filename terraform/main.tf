terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_account_name" {
  description = "Name of the service account for HMAC key rotation"
  type        = string
  default     = "hmac-rotator"
}

variable "gke_cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
}

variable "k8s_namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "default"
}

# Data sources
data "google_project" "current" {
  project_id = var.project_id
}

# Create custom IAM role for HMAC key management
resource "google_project_iam_custom_role" "hmac_rotator_role" {
  role_id     = "hmacKeyRotator"
  title       = "HMAC Key Rotator Role"
  description = "Custom role for HMAC key rotation with minimal permissions"
  project     = var.project_id

  permissions = [
    "storage.hmacKeys.create",
    "storage.hmacKeys.list",
    "storage.hmacKeys.update",
    "secretmanager.secrets.create",
    "secretmanager.secrets.get",
    "secretmanager.versions.add",
    "secretmanager.versions.list",
    "secretmanager.versions.disable"
  ]
}

# Service Account for HMAC key rotation
resource "google_service_account" "hmac_rotator" {
  account_id   = var.service_account_name
  display_name = "HMAC Key Rotator Service Account"
  description  = "Service account for automated HMAC key rotation"
  project      = var.project_id
}

# Bind the custom role to the service account
resource "google_project_iam_member" "hmac_rotator_role_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.hmac_rotator_role.name
  member  = "serviceAccount:${google_service_account.hmac_rotator.email}"
}

# Enable Workload Identity binding
resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.hmac_rotator.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/hmac-rotator-sa]"
}

# Create Secret Manager secret for HMAC keys
resource "google_secret_manager_secret" "gcs_hmac_key" {
  secret_id = "gcs-hmac-key"
  project   = var.project_id

  labels = {
    purpose     = "gcs-hmac-key"
    managed-by  = "terraform"
    auto-rotate = "true"
  }

  replication {
    auto {}
  }
}

# Outputs
output "service_account_email" {
  description = "Email of the created service account"
  value       = google_service_account.hmac_rotator.email
}

output "custom_role_name" {
  description = "Name of the custom IAM role"
  value       = google_project_iam_custom_role.hmac_rotator_role.name
}

output "secret_name" {
  description = "Name of the Secret Manager secret"
  value       = google_secret_manager_secret.gcs_hmac_key.secret_id
}

output "workload_identity_annotation" {
  description = "Annotation for Kubernetes Service Account"
  value       = "iam.gke.io/gcp-service-account=${google_service_account.hmac_rotator.email}"
}
