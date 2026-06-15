// ============================================================
// AIDA Jenkins 流水线（前后端分离 · 内网 Harbor · 自动部署）
//
// 功能：
//   1. Docker 镜像构建 + 推送（agent / manager / frontend 分别打包）
//   2. SSH 部署到 10.143.2.231（拉取镜像 + docker compose 重启）
//
// 凭据（Credentials Plugin）：
//   - harbor-aie（usernamePassword）
//   - ssh-231-root（SSH Username with private key）
//
// 配置文件（Config File Provider · 仅 agent/.env）：
//   - aida-231-agent-env  ← 模板见 jenkins/aida-231-agent.env.example
//
// 远程部署：scp compose + agent.env，ssh 内联 bash；Harbor 凭据经 stdin 登录，无临时文件
// Webhook 防抖：quietPeriod=1800（30 分钟），见 240 aida-deploy config.xml。
// ============================================================

pipeline {
    agent { label 'persistent && docker' }

    environment {
        DOCKER_BUILDKIT      = '1'
        DOCKER_REGISTRY      = 'harbor.aie.rnd.huawei.com'
        HARBOR_PROJECT       = 'aida'
        AGENT_IMAGE          = 'backend'
        MANAGER_IMAGE        = 'manager'
        FRONTEND_IMAGE       = 'frontend'
        DEPLOY_HOST          = '10.143.2.231'
        DEPLOY_DIR           = '/home/aida'
        CF_AGENT_ENV         = 'aida-231-agent-env'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds(abortPrevious: false)
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.GIT_BRANCH}, Commit: ${env.GIT_COMMIT}"
            }
        }

        stage('Docker Build & Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    script {
                        sh """
                            printf '%s' "\$DOCKER_PASS" | docker login ${DOCKER_REGISTRY} -u '${env.DOCKER_USER}' --password-stdin
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

        stage('Deploy') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'HARBOR_USER',
                    passwordVariable: 'HARBOR_PASS'
                )]) {
                    sshagent(credentials: ['ssh-231-root']) {
                        configFileProvider([
                            configFile(fileId: "${env.CF_AGENT_ENV}", targetLocation: 'agent.env'),
                        ]) {
                            sh """
                                set -e
                                ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} \\
                                    'mkdir -p ${DEPLOY_DIR}/agent ${DEPLOY_DIR}/logs/agent'
                                scp -o StrictHostKeyChecking=no docker-compose.yml \\
                                    root@${DEPLOY_HOST}:${DEPLOY_DIR}/
                                scp -o StrictHostKeyChecking=no agent.env \\
                                    root@${DEPLOY_HOST}:${DEPLOY_DIR}/agent/.env
                                printf '%s' "\$HARBOR_PASS" | ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} \\
                                    docker login ${DOCKER_REGISTRY} -u '${env.HARBOR_USER}' --password-stdin
                                ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} bash -s <<'EOS'
set -euo pipefail
cd ${DEPLOY_DIR}
mkdir -p logs/agent
docker compose pull
docker compose up -d --remove-orphans
docker compose ps
docker compose ps --status running | grep -q aida-agent
docker compose ps --status running | grep -q aida-manager
docker compose ps --status running | grep -q aida-frontend
docker image prune -f
docker logout ${DOCKER_REGISTRY} || true
echo '=== Container Status ==='
docker compose ps
EOS
                                rm -f agent.env
                            """
                        }
                    }
                }
            }
        }
    }

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
            ║  Config:   Managed file ${env.CF_AGENT_ENV}
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
