<?php
return [
  'authenticationMethod' => 'Oidc',
  'oidcClientId' => 'espocrm',
  'oidcClientSecret' => 'EspoCRMSecret2024',
  // На проде deploy.sh заменяет localhost:8000 -> публичный домен через sed.
  'oidcAuthorizationEndpoint' => 'http://localhost:8000/oauth/authorize',
  'oidcTokenEndpoint' => 'http://backend:8000/oauth/token',
  'oidcJwksEndpoint' => 'http://backend:8000/.well-known/jwks.json',
  'oidcUsernameClaim' => 'email',
  'oidcCreateUser' => true,
  'oidcAllowAdminUser' => true,
  'oidcScopes' => [
    0 => 'openid',
    1 => 'profile',
    2 => 'email'
  ],
  'database' => [
    'host' => 'espocrm-db',
    'port' => '3306',
    'charset' => NULL,
    'dbname' => 'espocrm',
    'user' => 'espocrm',
    'password' => 'espocrm_password',
    'platform' => 'Mysql'
  ],
  'smtpPassword' => NULL,
  'logger' => [
    'path' => 'data/logs/espo.log',
    'level' => 'WARNING',
    'rotation' => true,
    'maxFileNumber' => 30,
    'printTrace' => false,
    'databaseHandler' => false,
    'sql' => false,
    'sqlFailed' => false
  ],
  'restrictedMode' => false,
  'cleanupAppLog' => true,
  'cleanupAppLogPeriod' => '30 days',
  'webSocketMessager' => 'ZeroMQ',
  'clientSecurityHeadersDisabled' => false,
  'clientCspDisabled' => false,
  'clientCspScriptSourceList' => [
    0 => 'https://maps.googleapis.com'
  ],
  'adminUpgradeDisabled' => false,
  'isInstalled' => true,
  'microtimeInternal' => 1777492933.066964,
  'cryptKey' => '860fafc52c7803e50ef070765486b0d8',
  'hashSecretKey' => '82f5d4dd40ffba8b4f6ebb21944da1c4',
  'defaultPermissions' => [
    'user' => 'www-data',
    'group' => 'www-data'
  ],
  'actualDatabaseType' => 'mysql',
  'actualDatabaseVersion' => '8.0.46',
  'instanceId' => '858c4573-420d-4f1e-955a-b3b37205ce51'
];
