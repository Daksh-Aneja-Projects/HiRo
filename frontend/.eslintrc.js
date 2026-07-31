// This is a Create React App project written in JavaScript. The build lints
// with the `react-app` config (see package.json "eslintConfig"); this file
// makes the same rules available to a standalone `eslint`/editor run.
//
// It replaces a 300-line TypeScript+security config that demanded a tsconfig
// this JS app does not have and crashed ESLint on load, so no linting ran
// outside the build — which is how two `is not defined` render crashes shipped.
// `no-undef` is promoted to an error here as the guard against that recurring.
module.exports = {
  root: true,
  extends: ['react-app', 'react-app/jest'],
  rules: {
    'no-undef': 'error',
  },
};
