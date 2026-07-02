locals {
  connection = {
    type        = "ssh"
    host        = var.vps_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = var.ssh_private_key != "" ? var.ssh_private_key : null
    password    = var.vps_password != "" ? var.vps_password : null
    timeout     = "3m"
  }

  portfolio_config = templatefile("${path.module}/templates/portfolio-app.env.tftpl", {
    apps_root          = var.apps_root
    portfolio_branch   = var.portfolio_branch
    portfolio_path     = var.portfolio_path
    portfolio_repo_url = var.portfolio_repo_url
    portfolio_upstream = var.portfolio_upstream
  })
}

resource "null_resource" "gateway_host" {
  triggers = {
    vps_host       = var.vps_host
    ssh_port       = tostring(var.ssh_port)
    domain         = var.domain
    infra_repo_url = var.infra_repo_url
    infra_branch   = var.infra_branch
    install_path   = var.install_path
    apps_root      = var.apps_root
    backups_root   = var.backups_root
  }

  connection {
    type        = local.connection.type
    host        = local.connection.host
    port        = local.connection.port
    user        = local.connection.user
    private_key = local.connection.private_key
    password    = local.connection.password
    timeout     = local.connection.timeout
  }

  provisioner "remote-exec" {
    inline = [
      "set -eu",
      "export DEBIAN_FRONTEND=noninteractive",
      "apt-get update",
      "apt-get install -y ca-certificates curl git gettext-base openssl ufw",
      "mkdir -p '${var.apps_root}' '${var.backups_root}' /etc/sgdev-infra/apps /etc/sgdev-infra/cicd /etc/sgdev-infra/secrets",
      "if [ -d '${var.install_path}/.git' ]; then git -C '${var.install_path}' fetch origin '${var.infra_branch}' && git -C '${var.install_path}' checkout '${var.infra_branch}' && git -C '${var.install_path}' pull --ff-only origin '${var.infra_branch}'; else rm -rf '${var.install_path}' && git clone --branch '${var.infra_branch}' '${var.infra_repo_url}' '${var.install_path}'; fi",
      "chmod +x '${var.install_path}'/scripts/*.sh",
      "'${var.install_path}'/scripts/install-host.sh",
      "'${var.install_path}'/scripts/proxy-up.sh",
      "ufw allow ${var.ssh_port}/tcp || true",
      "ufw allow 80/tcp || true",
      "ufw allow 443/tcp || true",
    ]
  }
}

resource "null_resource" "portfolio_app" {
  count      = var.configure_portfolio ? 1 : 0
  depends_on = [null_resource.gateway_host]

  triggers = {
    portfolio_repo_url = var.portfolio_repo_url
    portfolio_branch   = var.portfolio_branch
    portfolio_path     = var.portfolio_path
    portfolio_upstream = var.portfolio_upstream
    config_hash        = sha256(local.portfolio_config)
  }

  connection {
    type        = local.connection.type
    host        = local.connection.host
    port        = local.connection.port
    user        = local.connection.user
    private_key = local.connection.private_key
    password    = local.connection.password
    timeout     = local.connection.timeout
  }

  provisioner "file" {
    content     = local.portfolio_config
    destination = "/tmp/portfolio.env"
  }

  provisioner "remote-exec" {
    inline = [
      "set -eu",
      "install -m 0644 /tmp/portfolio.env /etc/sgdev-infra/apps/portfolio.env",
      "rm -f /tmp/portfolio.env",
      "mkdir -p '${var.apps_root}/portfolio'",
      "echo 'Portfolio app config written to /etc/sgdev-infra/apps/portfolio.env'",
      "echo 'Create ${var.apps_root}/portfolio/repo/.env with runtime secrets before first deploy if the repo requires it.'",
      "if [ -n '${var.portfolio_repo_url}' ]; then '${var.install_path}'/scripts/app-deploy.sh portfolio || true; fi",
    ]
  }
}
