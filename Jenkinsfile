pipeline {
    agent none
    options {
        timeout(time: 10, unit: 'MINUTES')
        buildDiscarder(logRotator(
            artifactNumToKeepStr: '32',
            numToKeepStr: '64'
        ))
    }
    stages {
        stage('Setup pypi credentials') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'om-pypi-index-url', variable: 'OM_PYPI_INDEX_URL'),
                    ])
                    {
                        env.OM_PYPI_INDEX_URL = "${OM_PYPI_INDEX_URL}"
                    }
                }
            }
        }
        stage('Run mypy typechecks') {
            agent {
                dockerfile {
                    filename 'docker/test/Dockerfile'
                    additionalBuildArgs "--build-arg TAG=3.8-buster --build-arg OM_PYPI_INDEX_URL=${env.OM_PYPI_INDEX_URL}"
                }
            }
            steps {
                sh '''
                mypy src --junit-xml testing/gw-unit-reports/mypy-report.xml
                '''
            }
            post {
                always {
                    junit 'testing/gw-unit-reports/mypy-report.xml'
                }
            }
        }

        stage('Checking migrations') {
            agent {
                dockerfile {
                    filename 'docker/test/Dockerfile'
                    additionalBuildArgs "--build-arg TAG=3.8-buster --build-arg OM_PYPI_INDEX_URL=${env.OM_PYPI_INDEX_URL}"
                }
            }
            steps {
                sh '''
                rm -f etc/gateway.db
                mkdir -p etc
                cd src
                git clean -fd
                alembic upgrade head
                alembic revision -m jenkins --autogenerate
                # Second autogenerate fails with "Target database is not up to date" if there where unexpected changes.
                if ! alembic revision -m jenkins --autogenerate; then
                    echo
                    file=$(git status -z gateway/alembic/versions | sed 's,?? src/,,')
                    cat "$file"
                    echo
                    exit 1
                fi
                '''
            }
            post {
                always {
                    sh '''
                        git clean -fd
                        '''
                }
            }
        }

        stage('Run python2 unittests') {
            agent {
                dockerfile {
                    filename 'docker/test/Dockerfile'
                    additionalBuildArgs '--build-arg TAG=2.7-stretch'
                }
            }
            steps {
                sh '''
                ./testing/unittests/run.sh
                '''
            }
            post {
                always {
                    junit 'testing/gw-unit-reports/*.xml'
                }
            }
        }

        stage('Run python3 unittests') {
            agent {
                dockerfile {
                    filename 'docker/test/Dockerfile'
                    additionalBuildArgs "--build-arg TAG=3.8-buster --build-arg OM_PYPI_INDEX_URL=${env.OM_PYPI_INDEX_URL}"
                }
            }
            steps {
                sh '''
                ./testing/unittests/run3.sh
                '''
            }
            post {
                always {
                    junit 'testing/gw-unit-reports-3/*.xml'
                }
            }
        }

        stage('Start integration tests') {
            when {
                anyOf {
                    branch 'master'
                    branch 'develop'
                }
            }
            steps {
                script {
                    build(job: 'gateway-integration', wait: false, parameters: [
                        [$class: 'StringParameterValue', name: 'TESTS_BRANCH_NAME', value: env.BRANCH_NAME],
                        [$class: 'StringParameterValue', name: 'GATEWAY_BRANCH_NAME', value: env.BRANCH_NAME],
                    ])
                }
            }
        }
    }
}
