// ============================================================
// AIDA Jenkins 流水线（前后端分离 · 内网 Harbor · 自动部署）
//
// 功能：
//   1. Docker 镜像构建 + 推送（agent / manager / frontend 分别打包）
//   2. SSH 部署到 10.143.2.231（拉取镜像 + docker compose 重启）
//
// 使用方式：
//   - 在 Jenkins 中创建 Pipeline 项目，指向本仓库
//   - 配置凭据 harbor-aie（usernamePassword 类型）
//   - 配置凭据 ssh-231-root（SSH Username with private key 类型）
//
// Webhook 防抖：quietPeriod=1800（30 分钟），见 240 aida-deploy config.xml。
// ============================================================

pipeline {
    // 固定常驻 Agent（agent-inbound-240），复用宿主机 Docker BuildKit 缓存
    agent { label 'persistent && docker' }

    // ── 环境变量（写死，不走参数）──
    environment {
        DOCKER_BUILDKIT   = '1'
        DOCKER_REGISTRY   = 'harbor.aie.rnd.huawei.com'
        HARBOR_PROJECT    = 'aida'
        AGENT_IMAGE       = 'backend'
        MANAGER_IMAGE     = 'manager'
        FRONTEND_IMAGE    = 'frontend'
        DEPLOY_HOST       = '10.143.2.231'
        DEPLOY_DIR        = '/home/aida'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds(abortPrevious: false)
    }

    stages {
        // ──────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.GIT_BRANCH}, Commit: ${env.GIT_COMMIT}"
            }
        }

        // ──────────────────────────────────────────────
        stage('Docker Build & Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    script {
                        sh """
                            echo \$DOCKER_PASS | docker login ${DOCKER_REGISTRY} -u \$DOCKER_USER --password-stdin
                        """

                        sh """
                            docker build -f agent/Dockerfile \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER} \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest .
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest
                        """
                        env.AGENT_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}"

                        sh """
                            docker build -f manager/Dockerfile \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${MANAGER_IMAGE}:${env.BUILD_NUMBER} \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${MANAGER_IMAGE}:latest .
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${MANAGER_IMAGE}:${env.BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${MANAGER_IMAGE}:latest
                        """
                        env.MANAGER_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${MANAGER_IMAGE}:${env.BUILD_NUMBER}"

                        sh """
                            docker build -f frontend/Dockerfile \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER} \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest .
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest
                        """
                        env.FRONTEND_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}"

                        sh "docker logout ${DOCKER_REGISTRY}"
                    }
                }
            }
        }

        // ──────────────────────────────────────────────
        stage('Deploy') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'HARBOR_USER',
                    passwordVariable: 'HARBOR_PASS'
                )]) {
                    sshagent(credentials: ['ssh-231-root']) {
                        script {
                            writeFile file: 'harbor-deploy.env', text: """\
HARBOR_PASS=${env.HARBOR_PASS}
HARBOR_USER='${env.HARBOR_USER}'
REGISTRY=${env.DOCKER_REGISTRY}
"""
                            writeFile file: 'deploy-remote.sh', text: """\
#!/usr/bin/env bash
set -euo pipefail
cd ${env.DEPLOY_DIR}
set -a
source /tmp/harbor-deploy.env
set +a
printf '%s' "\$HARBOR_PASS" | docker login "\$REGISTRY" -u "\$HARBOR_USER" --password-stdin
if [[ ! -f agent/.env ]]; then
  echo 'WARN: /home/aida/agent/.env 不存在，manager 将 unhealthy。请 cp agent/.env.example agent/.env 并填入 DATA_CENTER_BASE_URL、ZHIPU_API_KEY' >&2
fi
docker compose pull
docker compose up -d --remove-orphans
docker compose ps
docker compose ps --status running | grep -q aida-agent
docker compose ps --status running | grep -q aida-manager
docker compose ps --status running | grep -q aida-frontend
docker image prune -f
docker logout "\$REGISTRY" || true
rm -f /tmp/harbor-deploy.env /tmp/deploy-remote.sh
echo '=== Container Status ==='
docker compose ps
"""
                            sh """
                                set -e
                                ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} 'mkdir -p ${DEPLOY_DIR}/agent'
                                scp -o StrictHostKeyChecking=no docker-compose.yml root@${DEPLOY_HOST}:${DEPLOY_DIR}/
                                scp -o StrictHostKeyChecking=no agent/.env.example root@${DEPLOY_HOST}:${DEPLOY_DIR}/agent/.env.example
                                scp -o StrictHostKeyChecking=no harbor-deploy.env deploy-remote.sh root@${DEPLOY_HOST}:/tmp/
                                ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} 'chmod +x /tmp/deploy-remote.sh && bash /tmp/deploy-remote.sh'
                                rm -f harbor-deploy.env deploy-remote.sh
                            """
                        }
                    }
                }
            }
        }
    }

    // ── 构建后清理 ──
    post {
        success {
            echo """
            ╔══════════════════════════════════════════════════╗
            ║  AIDA Build + Deploy Success                     ║
            ║  Agent:    ${env.AGENT_FULL_IMAGE ?: 'N/A'}
            ║  Manager:  ${env.MANAGER_FULL_IMAGE ?: 'N/A'}
            ║  Frontend: ${env.FRONTEND_FULL_IMAGE ?: 'N/A'}
            ║  Deploy:   ${env.DEPLOY_HOST}:${env.DEPLOY_DIR}
            ║
            ║  URL:      https://aida.rnd.huawei.com
            ║  调试(可选): http://${env.DEPLOY_HOST}:18080  (compose ports 取消注释)
            ║  首次:     ${env.DEPLOY_DIR}/agent/.env 须含 DATA_CENTER_BASE_URL + ZHIPU_API_KEY
            ║
            ║  Branch:   ${env.GIT_BRANCH}
            ║  Commit:   ${env.GIT_COMMIT?.take(7) ?: 'N/A'}
            ╚══════════════════════════════════════════════════╝
            """
        }
        failure {
            echo "AIDA build failed, check logs"
        }
        always {
            sh 'docker image prune -f || true'
        }
    }
}
