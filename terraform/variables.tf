variable "vps_host" {
  description = "Public IP or DNS name of the VPS."
  type        = string
  default     = "143.95.217.87"
}

variable "ssh_port" {
  description = "SSH port exposed by the VPS."
  type        = number
  default     = 22022
}

variable "ssh_user" {
  description = "SSH user used by Terraform."
  type        = string
  default     = "root"
}

variable "ssh_private_key" {
  description = "Private key for SSH. Prefer this over password auth."
  type        = string
  default     = ""
  sensitive   = true
}

variable "vps_password" {
  description = "SSH password fallback. Keep only in TF_VAR_vps_password or GitHub Secrets."
  type        = string
  default     = ""
  sensitive   = true
}

variable "domain" {
  description = "Primary public domain for the gateway."
  type        = string
  default     = "sgdev.com.ar"
}

variable "infra_repo_url" {
  description = "Git URL of this gateway repo, used by the VPS to pull updates."
  type        = string
}

variable "infra_branch" {
  description = "Branch to checkout for the gateway repo."
  type        = string
  default     = "main"
}

variable "install_path" {
  description = "Path where the gateway repository is installed on the VPS."
  type        = string
  default     = "/opt/sgdev-infra"
}

variable "apps_root" {
  description = "Base path where application repositories are cloned."
  type        = string
  default     = "/opt/apps"
}

variable "backups_root" {
  description = "Base path where app backups are stored."
  type        = string
  default     = "/opt/backups"
}

variable "configure_portfolio" {
  description = "When true, writes the portfolio app config and runs its deploy script."
  type        = bool
  default     = false
}

variable "portfolio_repo_url" {
  description = "Git URL of the portfolio repository."
  type        = string
  default     = ""
}

variable "portfolio_branch" {
  description = "Portfolio branch to deploy."
  type        = string
  default     = "main"
}

variable "portfolio_path" {
  description = "Public path for the portfolio behind the gateway."
  type        = string
  default     = "/portfolio"
}

variable "portfolio_upstream" {
  description = "Gateway upstream for the portfolio internal Nginx."
  type        = string
  default     = "http://host.docker.internal:18080"
}
