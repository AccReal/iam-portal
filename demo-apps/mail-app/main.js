// Mail demo-app entry point — all logic is in ../shared/app-runtime.js.
const path = require('path');
const { createRuntime } = require('../shared/app-runtime');
const appIds = require('../shared/app-ids');

createRuntime({
  appId: appIds.MAIL,
  title: 'Корпоративная почта',
  iconPath: path.join(__dirname, 'icon.png'),
  appDir: __dirname,
});
