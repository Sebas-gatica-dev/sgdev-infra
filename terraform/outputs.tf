output "gateway_http_url" {
  value       = "http://${var.domain}"
  description = "Public HTTP gateway URL."
}

output "portfolio_url" {
  value       = "http://${var.domain}${var.portfolio_path}/"
  description = "Portfolio URL behind the gateway."
}

output "vps_target" {
  value       = "${var.ssh_user}@${var.vps_host}:${var.ssh_port}"
  description = "SSH target used by Terraform and deploy workflows."
}
