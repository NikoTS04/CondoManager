"use strict";

// Reuse the complete OpenAPI validator from the running Spectral CLI, including npx.
const cliRequire = require("module").createRequire(process.argv[1]);
module.exports = cliRequire(
  "@stoplight/spectral-rulesets/dist/oas/functions/oasDocumentSchema",
).default;
