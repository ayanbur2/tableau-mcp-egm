/**
 * Custom Tableau MCP feature gate — enable all documented tool surfaces locally.
 * Docs: https://tableau.github.io/tableau-mcp/docs/developers/feature-flags
 */
const DEFAULTS = {
  'mcp-apps': true,
  'interactive-viz': true,
  'mcp-apps-for-claude': true,
  'enforce-role-requirements': true,
  'enforce-registration-conditions': true,
  'datasource-authoring': true,
  'flow-read-tools': true,
  'flow-write-tools': true,
  'knowledge-tools': true,
  'knowledge-write-tools': true,
  'view-file-mode': true,
  'view-data-file-mode': true,
  'workbook-file-mode': true,
  'data-apps': true,
  'view-all-data': true,
  'skills-over-mcp': true,
  'authoring-with-slack': true,
  'activity-log': true,
  'admin-tools': true,
  'disable-strict-scope-match': false,
};

class FeatureGateProvider {
  async isFeatureEnabled(featureName) {
    if (Object.prototype.hasOwnProperty.call(DEFAULTS, featureName)) {
      return DEFAULTS[featureName];
    }
    // Unknown flags default on for local full-tool mode.
    return true;
  }
}

module.exports = FeatureGateProvider;
module.exports.FeatureGateProvider = FeatureGateProvider;
module.exports.default = FeatureGateProvider;
