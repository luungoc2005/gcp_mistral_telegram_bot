REGION=asia-southeast1
PYTHON_VERSION=python39
ENV_VARS_FILE=.env.yaml
TELEGRAM_TOKEN=$(yq '.TELEGRAM_TOKEN' $ENV_VARS_FILE)
GOOGLE_CLOUD_PROJECT_ID=$(yq '.GOOGLE_CLOUD_PROJECT_ID' $ENV_VARS_FILE)
PUBSUB_TOPIC_NAME=$(yq '.PUBSUB_TOPIC_NAME' $ENV_VARS_FILE)

gcloud functions deploy telegram_webhook \
  --entry-point telegram_webhook \
  --env-vars-file $ENV_VARS_FILE \
  --runtime $PYTHON_VERSION \
  --trigger-http \
  --allow-unauthenticated \
  --region $REGION \
  --gen2
gcloud functions deploy handle_message \
  --entry-point handle_message \
  --env-vars-file $ENV_VARS_FILE \
  --runtime $PYTHON_VERSION \
  --trigger-topic $PUBSUB_TOPIC_NAME \
  --region $REGION \
  --cpu 4 \
  --memory 16Gi \
  --timeout 3600s \
  --gen2

curl -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=https://$REGION-$GOOGLE_CLOUD_PROJECT_ID.cloudfunctions.net/telegram_webhook"