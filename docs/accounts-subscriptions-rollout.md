# Accounts And Subscriptions Rollout

Authentication, quotas, and billing must be validated in personal-dev before production changes.

## Dev Infrastructure

1. Keep EC2 stopped while reviewing Terraform.
2. Reinitialize the local AWS provider if validation reports a plugin handshake failure.
3. Apply the personal-dev workspace with `enable_cognito_auth=true`.
4. Record Terraform outputs `cognito_user_pool_id`, `cognito_mobile_app_client_id`, and `user_access_table_name`.
5. Add those values as GitHub dev environment variables:
   - `DIALEDIN_COGNITO_USER_POOL_ID`
   - `DIALEDIN_COGNITO_APP_CLIENT_ID`
   - `DIALEDIN_USAGE_TABLE`
6. Do not enable production authentication until the dev build passes signup, quota, purchase, restore, expiration, and deletion tests.

## Mobile Build Variables

- `EXPO_PUBLIC_AUTH_ENABLED=true`
- `EXPO_PUBLIC_COGNITO_REGION=us-east-1`
- `EXPO_PUBLIC_COGNITO_APP_CLIENT_ID=<dev Terraform output>`
- `EXPO_PUBLIC_REVENUECAT_IOS_API_KEY=<RevenueCat public iOS SDK key>`

Public RevenueCat SDK keys and the Cognito client ID are build configuration, not secrets. The RevenueCat webhook authorization value is a backend secret and must never use an `EXPO_PUBLIC_` variable.

## App Store And RevenueCat

1. Create one subscription group in App Store Connect.
2. Create annual product `dialedin_pro_annual` at the USD 19.99 equivalent price point.
3. Create RevenueCat entitlement `pro`.
4. Attach the annual product to the current offering as its annual package.
5. Configure the dev webhook as `https://api-dev.dialedin.me/webhooks/revenuecat`.
6. Set a strong Authorization header in RevenueCat and the matching backend secret.
7. Test with an App Store sandbox account in a native development/TestFlight build. Expo Go cannot perform real in-app purchases.

## Release Gate

Verify signup, verification, login, refresh, password reset, three free analyses, fourth-request rejection, annual sandbox purchase, webhook-backed Pro status, restore purchases, expiration/refund handling, sign-out, and in-app account deletion.

