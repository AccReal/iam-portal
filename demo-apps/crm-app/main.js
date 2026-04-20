// CRM demo-app entry point.
// All SSO / session / window orchestration lives in the shared runtime;
// this file just declares the app's identity.
const path = require('path');
const { createRuntime } = require('../shared/app-runtime');
const appIds = require('../shared/app-ids');

createRuntime({
  appId: appIds.CRM,
  title: 'CRM Система',
  iconPath: path.join(__dirname, 'icon.png'),
  appDir: __dirname,
});
