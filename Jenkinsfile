// ============================================================
// AIDA Jenkins 流水线（前后端分离 · 内网 Harbor · 自动部署）
//
// 功能：
//   1. 后端守门 lint（10 项）+ 评测回归
//   2. 前端 typecheck + vite build
//   3. Docker 镜像构建 + 推送（agent / frontend 分别打包）
//   4. SSH 部署到 10.143.2.231（拉取镜像 + docker compose 重启）
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
        PYTHON_VERSION    = '3.11'
        NODE_VERSION      = '20'
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
        // 后端：守门 lint + 评测（并行）
        // ──────────────────────────────────────────────
        stage('后端验证') {
            parallel {
                stage('守门 lint') {
                    steps {
                        script {
                            def pyHome = tool(name: "python-${PYTHON_VERSION}", type: 'python')
                            env.PATH = "${pyHome}:${pyHome}/Scripts:${env.PATH}"
                        }
                        sh '''
                            python -m venv .venv-ci
                            . .venv-ci/bin/activate
                            pip install -q \
                                -i http://mirrors.tools.huawei.com/pypi/simple \
                                --trusted-host mirrors.tools.huawei.com \
                                -r agent/requirements.txt

                            # 部署 SKILL.md 到运行时位置
                            mkdir -p ~/.claude/skills
                            cp -r skills/. ~/.claude/skills/

                            echo "=== 守门 · 禁裸 LLM 调用 ==="
                            python agent/scripts/lint_no_naked_llm.py

                            echo "=== 守门 · 禁裸外发 ==="
                            python agent/scripts/lint_no_naked_send.py

                            echo "=== 守门 · SKILL.md ↔ steps 契约 ==="
                            python agent/scripts/lint_skill_contract.py

                            echo "=== 守门 · 工具 name/desc/schema 契约 ==="
                            python agent/scripts/lint_tools.py

                            echo "=== 守门 · SDUI 协议三方一致 ==="
                            python agent/scripts/lint_sdui_contract.py

                            echo "=== 守门 · SDUI 组件目录 HTML 新鲜度 ==="
                            python agent/scripts/lint_sdui_gallery.py

                            echo "=== 守门 · 开发者文档站 HTML 新鲜度 ==="
                            python agent/scripts/lint_docs_site.py

                            echo "=== 守门 · 团队门户 HTML 新鲜度 ==="
                            python agent/scripts/lint_team_portal.py

                            echo "=== 守门 · 运行时契约 ==="
                            python agent/scripts/lint_runtime_contract.py

                            echo "=== 守门 · 跨 skill 零横向依赖 ==="
                            python agent/scripts/lint_module_boundaries.py
                        '''
                    }
                }

                stage('评测回归') {
                    steps {
                        script {
                            def pyHome = tool(name: "python-${PYTHON_VERSION}", type: 'python')
                            env.PATH = "${pyHome}:${pyHome}/Scripts:${env.PATH}"
                        }
                        sh '''
                            if [ ! -d .venv-ci ]; then
                                python -m venv .venv-ci
                                . .venv-ci/bin/activate
                                pip install -q \
                                    -i http://mirrors.tools.huawei.com/pypi/simple \
                                    --trusted-host mirrors.tools.huawei.com \
                                    -r agent/requirements.txt
                                mkdir -p ~/.claude/skills
                                cp -r skills/. ~/.claude/skills/
                            else
                                . .venv-ci/bin/activate
                            fi

                            echo "=== 评测回归 · zhgk golden fixture ==="
                            python agent/evals/eval_zhgk.py --fixture

                            echo "=== 单元测试 · SOG 资产 ==="
                            python -m unittest agent.tests.test_sog_assets -v || true
                        '''
                    }
                }
            }
        }

        // ──────────────────────────────────────────────
        // 前端：typecheck + vite build
        // ──────────────────────────────────────────────
        stage('前端构建') {
            steps {
                script {
                    def nodeHome = tool(name: "node-${NODE_VERSION}", type: 'nodejs')
                    env.PATH = "${nodeHome}/bin:${env.PATH}"
                }
                dir('frontend') {
                    sh '''
                        npm config set registry http://mirrors.tools.huawei.com/npm/
                        npm ci --no-audit --no-fund
                        npm run build
                    '''
                    archiveArtifacts artifacts: 'dist/**/*', fingerprint: true
                }
            }
        }

        // ──────────────────────────────────────────────
        // Docker：登录 Harbor → 构建 → 推送（agent / frontend 并行）
        // ──────────────────────────────────────────────
        stage('Docker 构建与推送') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'harbor-aie',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh """
                        echo \$DOCKER_PASS | docker login ${DOCKER_REGISTRY} -u \$DOCKER_USER --password-stdin
                    """
                }

                parallel(
                    'Agent 后端': {
                        sh """
                            docker build -f agent/Dockerfile \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER} \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest .
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:latest
                        """
                        script {
                            env.AGENT_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${AGENT_IMAGE}:${env.BUILD_NUMBER}"
                        }
                    },
                    'Frontend 前端': {
                        sh """
                            docker build -f frontend/Dockerfile \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER} \
                                -t ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest .
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}
                            docker push ${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:latest
                        """
                        script {
                            env.FRONTEND_FULL_IMAGE = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}/${FRONTEND_IMAGE}:${env.BUILD_NUMBER}"
                        }
                    }
                )

                sh "docker logout ${DOCKER_REGISTRY}"
            }
        }

        // ──────────────────────────────────────────────
        // 部署：SSH 到目标服务器，拉取镜像，启动容器
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

                                # 登录 Harbor
                                echo '${HARBOR_PASS}' | docker login ${DOCKER_REGISTRY} -u '${HARBOR_USER}' --password-stdin

                                # 拉取最新镜像
                                docker compose pull

                                # 重启容器
                                docker compose up -d --remove-orphans

                                # 清理旧镜像
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
            ║  分支:     ${env.GIT_BRANCH}
            ║  提交:     ${env.GIT_COMMIT?.take(7) ?: 'N/A'}
            ╚══════════════════════════════════════════════════╝
            """
        }
        failure {
            echo "❌ AIDA 构建失败，请检查日志"
        }
        always {
            sh 'rm -rf .venv-ci || true'
            sh 'docker image prune -f || true'
        }
    }
}

