def SERVICES = ['tools', 'customers', 'rentals', 'maintenance', 'web']

def COMPOSE_PROJECT = 'construction_tool_rental1'

def isMain() {
    def b = env.GIT_BRANCH ?: env.BRANCH_NAME ?: ''
    return b == 'main' || b == 'origin/main' || b == 'refs/heads/main'
}

pipeline {
    agent any

    environment {
        DOCKER_CREDENTIALS_ID = 'docker-hub-credentials'
        IMAGE_PREFIX          = 'koptelovkir535363/tool-rental'
        IMAGE_TAG             = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Run tests') {
            steps {
                bat "docker build -f Dockerfile.test -t ${env.IMAGE_PREFIX}-tests:${env.IMAGE_TAG} ."
                bat "docker run --rm ${env.IMAGE_PREFIX}-tests:${env.IMAGE_TAG}"
            }
        }

        stage('Build Docker images') {
            steps {
                script {
                    for (s in SERVICES) {
                        bat "docker build -f services/${s}/Dockerfile " +
                            "-t ${env.IMAGE_PREFIX}-${s}:${env.IMAGE_TAG} " +
                            "-t ${env.IMAGE_PREFIX}-${s}:latest ."
                    }
                }
            }
        }

        stage('Push to Docker Hub') {
            when { expression { return isMain() } }
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', env.DOCKER_CREDENTIALS_ID) {
                        for (s in SERVICES) {
                            docker.image("${env.IMAGE_PREFIX}-${s}:${env.IMAGE_TAG}").push()
                            docker.image("${env.IMAGE_PREFIX}-${s}:latest").push()
                        }
                    }
                }
            }
        }

        stage('Deploy to main') {
            when { expression { return isMain() } }
            steps {
                bat 'echo IMAGE_TAG=[%IMAGE_TAG%]'
                bat "docker compose -p ${COMPOSE_PROJECT} build"
                bat "docker compose -p ${COMPOSE_PROJECT} up -d --no-build"

                bat """
                    echo Проверка доступности сайта через Nginx

                    powershell -NoProfile -ExecutionPolicy Bypass -Command "\$ok = \$false; for (\$i = 0; \$i -lt 20; \$i++) { try { \$r = Invoke-WebRequest -Uri 'http://127.0.0.1/' -UseBasicParsing -TimeoutSec 3; if (\$r.StatusCode -eq 200) { \$ok = \$true; break } } catch {}; Start-Sleep -Seconds 3 }; if (-not \$ok) { exit 1 }"

                    if errorlevel 1 (
                        echo ОШИБКА: сайт не отвечает.
                        docker compose -p ${COMPOSE_PROJECT} ps
                        docker compose -p ${COMPOSE_PROJECT} logs --tail=100
                        exit /b 1
                    )

                    echo Сайт успешно запущен: http://localhost
                """
            }
        }
    }

    post {
        success { echo 'Тесты, сборка образов, push и деплой завершены успешно.' }
        failure { echo 'Ошибка на одном из этапов.' }
        always  { echo 'Pipeline завершён.' }
    }
}