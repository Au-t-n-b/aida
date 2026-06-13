// ============================================================
// AIDA Jenkins 流水线（前后端分离 · 内网 Harbor）
//
// 功能：
//   1. 后端守门 lint（10 项）+ 评测回归
//   2. 前端 typecheck + vite build
//   3. Docker 镜像构建 + 推送（agent / frontend 分别打包）
//
// 使用方式：
//   - 在 Jenkins 中创建 Pipeline 项目，指向本仓库
//   - 配置凭据 harbor-aie（usernamePassword 类型）
//   - 配置参数（可选）：SKIP_DOCKER_PUSH、HARBOR_PROJECT 等
// ============================================================

pipeline {
    agent any

    // ── 环境变量 ──
    environment {
        DOCKER_REGISTRY   = 'harbor.aie.rnd.huawei.com'
        HARBOR_PROJECT    = "${params.HARBOR_PROJECT ?: 'library'}"
        AGENT_IMAGE       = "${params.AGENT_IMAGE ?: 'aida-agent'}"
        FRONTEND_IMAGE    = "${params.FRONTEND_IMAGE ?: 'aida-frontend'}"
        IMAGE_TAG         = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'latest'}"
        PYTHON_VERSION    = '3.11'
        NODE_VERSION      = '20'
    }

    // ── 构建参数（Jenkins UI 可覆盖）──
    parameters {
        string(name: 'HARBOR_PROJECT',  defaultValue: 'library',    description: 'Harbor 项目名（镜像路径中的命名空间）')
        string(name: 'AGENT_IMAGE',     defaultValue: 'aida-agent', description: '后端镜像名称')
        string(name: 'FRONTEND_IMAGE',  defaultValue: 'aida-frontend', description: '前端镜像名称')
        booleanParam(name: 'SKIP_DOCKER_PUSH', defaultValue: false, description: '跳过 Docker 推送（仅本地构建）')
        booleanParam(name: 'SKIP_LINT',        defaultValue: false, description: '跳过后端守门 lint')
        booleanParam(name: 'SKIP_EVAL',        defaultValue: false, description: '跳过评测回归')
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
                    when { expression { !params.SKIP_LINT } }
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
                    when { expression { !params.SKIP_EVAL } }
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
                // 先统一登录 Harbor（基础镜像也从此拉取）
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
                        script {
                            def baseReg   = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}"
                            def tag       = "${baseReg}/${AGENT_IMAGE}:${IMAGE_TAG}"
                            def latest    = "${baseReg}/${AGENT_IMAGE}:latest"

                            sh "docker build -f agent/Dockerfile --build-arg REGISTRY=${baseReg} -t ${tag} -t ${latest} ."
                            env.AGENT_FULL_IMAGE = tag

                            if (!params.SKIP_DOCKER_PUSH) {
                                sh "docker push ${tag}"
                                sh "docker push ${latest}"
                            }
                        }
                    },
                    'Frontend 前端': {
                        script {
                            def baseReg   = "${DOCKER_REGISTRY}/${HARBOR_PROJECT}"
                            def tag       = "${baseReg}/${FRONTEND_IMAGE}:${IMAGE_TAG}"
                            def latest    = "${baseReg}/${FRONTEND_IMAGE}:latest"

                            sh "docker build -f frontend/Dockerfile --build-arg REGISTRY=${baseReg} -t ${tag} -t ${latest} ."
                            env.FRONTEND_FULL_IMAGE = tag

                            if (!params.SKIP_DOCKER_PUSH) {
                                sh "docker push ${tag}"
                                sh "docker push ${latest}"
                            }
                        }
                    }
                )

                // 构建完成后登出
                sh "docker logout ${DOCKER_REGISTRY}"
            }
        }
    }

    // ── 构建后清理 ──
    post {
        success {
            echo """
            ╔══════════════════════════════════════════════════╗
            ║  ✅ AIDA 构建成功                                ║
            ║  Agent:    ${env.AGENT_FULL_IMAGE ?: 'N/A'}
            ║  Frontend: ${env.FRONTEND_FULL_IMAGE ?: 'N/A'}
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
