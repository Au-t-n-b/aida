// ============================================================
// AIDA Jenkins 流水线（前后端分离 · 内网 Harbor · 自动部署）
//
// 功能：
//   1. Docker 镜像构建 + 推送（agent / frontend 分别打包）
//   2. SSH 部署到 10.143.2.231（拉取镜像 + docker compose 重启）
//
// 使用方式：
//   - 在 Jenkins 中创建 Pipeline 项目，指向本仓库
//   - 配置凭据 harbor-aie（usernamePassword 类型）
//   - 配置凭据 ssh-231-root（SSH Username with private key 类型）
// ============================================================

pipeline {
    agent any

    // ── 环境变量（写死，不走参数）──
    environment {
        DOCKER_REGISTRY   = 'harbor.aie.rnd.huawei.com'
        HARBOR_PROJECT    = 'library'
        AGENT_IMAGE       = 'aida-agent'
        FRONTEND_IMAGE    = 'aida-frontend'
        DEPLOY_HOST       = '10.143.2.231'
        DEPLOY_DIR        = '/home/docker_data/aida'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        // ──────────────────────────────────────────────
        stage('检出代码') {
            steps {
                checkout scm
                echo "分支: ${env.GIT_BRANCH}, 提交: ${env.GIT_COMMIT}"
            }
        }

        // ──────────────────────────────────────────────
        stage('Docker 构建与推送') {
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

                        parallel(
                            'Agent 后端': {
                                sh """
                                    docker build -f agent/Dockerfile \
                                        -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER} \
                                        -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest .
                                    docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}
                                    docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest
                                """
                                env.AGENT_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}"
                            },
                            'Frontend 前端': {
                                sh """
                                    docker build -f frontend/Dockerfile \
                                        -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER} \
                                        -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest .
                                    docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}
                                    docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest
                                """
                                env.FRONTEND_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}"
                            }
                        )

                        sh "docker logout ${DOCKER_REGISTRY}"
                    }
                }
            }
        }

        // ──────────────────────────────────────────────
        stage('部署到服务器') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'HARBOR_USER',
                    passwordVariable: 'HARBOR_PASS'
                )]) {
                    sshagent(credentials: ['ssh-231-root']) {
                        sh """
                            set -e

                            # 创建部署目录
                            ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} 'mkdir -p ${DEPLOY_DIR}'

                            # 推送 docker-compose.yml 到服务器
                            scp -o StrictHostKeyChecking=no docker-compose.yml root@${DEPLOY_HOST}:${DEPLOY_DIR}/

                            # 远程执行：登录 Harbor → 拉取镜像 → 重启容器
                            ssh -o StrictHostKeyChecking=no root@${DEPLOY_HOST} "
                                cd ${DEPLOY_DIR}

                                echo '${HARBOR_PASS}' | docker login ${DOCKER_REGISTRY} -u '${HARBOR_USER}' --password-stdin

                                docker compose pull
                                docker compose up -d --remove-orphans
                                docker image prune -f
                                docker logout ${DOCKER_REGISTRY}

                                echo '=== 容器状态 ==='
                                docker compose ps
                            "
                        """
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
            ║  ✅ AIDA 构建 + 部署成功                         ║
            ║  Agent:    ${env.AGENT_FULL_IMAGE ?: 'N/A'}
            ║  Frontend: ${env.FRONTEND_FULL_IMAGE ?: 'N/A'}
            ║  部署到:   ${env.DEPLOY_HOST}:${env.DEPLOY_DIR}
            ║
            ║  🌐 前端访问: http://${env.DEPLOY_HOST}:5401
            ║  🔧 后端 API: http://${env.DEPLOY_HOST}:7401
            ║
            ║  分支:     ${env.GIT_BRANCH}
            ║  提交:     ${env.GIT_COMMIT?.take(7) ?: 'N/A'}
            ╚══════════════════════════════════════════════════╝
            """
        }
        failure {
            echo "❌ AIDA 构建失败，请检查日志"
        }
        always {
            sh 'docker image prune -f || true'
        }
    }
}
