# DialedIn Privacy Policy

**Effective date:** September 3, 2026

DialedIn provides espresso equipment guidance and AI-assisted shot analysis. This policy describes the information handled by the DialedIn mobile application and cloud service.

## Information We Handle

- Account information: email address, Cognito account identifier, and authentication metadata.
- Espresso information: selected equipment, grind settings, dose, roast, taste notes, timing, recommendations, and shot history.
- Media: machine or grinder photos and shot audio/video selected by the user.
- Purchase information: subscription product, entitlement state, renewal or expiration time, and store transaction identifiers supplied by RevenueCat. DialedIn does not receive full payment-card details.
- Operations information: request timing, errors, device/app version, and aggregate service metrics. Logs must not contain raw account passwords or media content.

## How We Use Information

We use this information to authenticate accounts, provide analysis and recommendations, maintain history, enforce usage allowances, restore subscriptions, prevent abuse, operate the service, and troubleshoot failures.

Media is stored privately in Amazon S3 and is accessed only to provide requested features. Reviewed public equipment images are separate from private user uploads.

## Service Providers

DialedIn uses Amazon Web Services, including Cognito, S3, DynamoDB, Bedrock, CloudFront, and CloudWatch. RevenueCat processes subscription status, while Apple or Google processes native payments.

## Retention And Deletion

Account data and shot history are retained while the account exists. A user can choose **Account > Delete account** in the app. This removes the user's shot history, entitlement and usage records, and all versions of private media under the user's storage prefix, then deletes the Cognito identity. Store subscription cancellation is managed separately through Apple or Google.

Operational logs and backups may remain for a limited period where required for security, reliability, fraud prevention, or legal compliance.

## Security

DialedIn uses encrypted HTTPS connections, private S3 storage, server-side token verification, and restricted cloud permissions. No internet service can guarantee absolute security.

## Contact

Privacy questions and deletion support: support@dialedin.me

