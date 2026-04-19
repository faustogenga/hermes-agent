(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    Badge,
    Button,
    Input,
    Label,
    OAuthProvidersCard,
  } = SDK.components;
  const { useState, useEffect } = SDK.hooks;

  function tokenHelp(envKey) {
    if (envKey === "COPILOT_GITHUB_TOKEN") {
      return "Use this only if you specifically want GitHub Copilot / GitHub Models auth separate from your general GitHub repo token.";
    }
    if (envKey === "GH_TOKEN") {
      return "GH_TOKEN is also picked up by the gh CLI. Choose this if you want Hermes and gh to share the same token.";
    }
    return "GITHUB_TOKEN is the recommended default for dashboard-based GitHub access, repo inspection, and push/pull automation.";
  }

  function Pill(props) {
    return React.createElement(
      "span",
      {
        className:
          "inline-flex items-center rounded border border-border px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground",
      },
      props.children,
    );
  }

  function RepoPermissionBadges(props) {
    const permissions = props.permissions || {};
    return React.createElement(
      "div",
      { className: "flex flex-wrap gap-2" },
      React.createElement(Badge, { variant: permissions.pull ? "success" : "outline" }, permissions.pull ? "pull" : "no pull"),
      React.createElement(Badge, { variant: permissions.push ? "success" : "outline" }, permissions.push ? "push" : "no push"),
      React.createElement(Badge, { variant: permissions.admin ? "success" : "outline" }, permissions.admin ? "admin" : "no admin"),
    );
  }

  function ConnectionsPage() {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [tokenValue, setTokenValue] = useState("");
    const [tokenKey, setTokenKey] = useState("GITHUB_TOKEN");
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);

    function refreshStatus() {
      setLoading(true);
      setError(null);
      SDK.fetchJSON("/api/plugins/connections/github/status")
        .then(function (data) {
          setStatus(data);
          if (data && data.token_source) {
            setTokenKey(data.token_source);
          }
        })
        .catch(function (err) {
          setError(String(err));
        })
        .finally(function () {
          setLoading(false);
        });
    }

    useEffect(function () {
      refreshStatus();
    }, []);

    function saveToken() {
      if (!tokenValue.trim()) return;
      setSaving(true);
      setMessage(null);
      setError(null);
      SDK.api
        .setEnvVar(tokenKey, tokenValue.trim())
        .then(function () {
          setMessage("GitHub token saved. Re-checking access…");
          setTokenValue("");
          refreshStatus();
        })
        .catch(function (err) {
          setError("Failed to save token: " + err);
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function clearCurrentToken() {
      if (!status || !status.token_source) return;
      setSaving(true);
      setMessage(null);
      setError(null);
      SDK.api
        .deleteEnvVar(status.token_source)
        .then(function () {
          setMessage("Cleared " + status.token_source + ".");
          refreshStatus();
        })
        .catch(function (err) {
          setError("Failed to clear token: " + err);
        })
        .finally(function () {
          setSaving(false);
        });
    }

    const repo = status && status.repo ? status.repo : {};
    const currentRepoAccess = status && status.current_repo_access ? status.current_repo_access : null;

    return React.createElement(
      "div",
      { className: "flex flex-col gap-6" },
      React.createElement(
        Card,
        null,
        React.createElement(
          CardHeader,
          null,
          React.createElement(
            "div",
            { className: "flex items-center gap-3 flex-wrap" },
            React.createElement(CardTitle, { className: "text-lg" }, "Connections"),
            React.createElement(Badge, { variant: "outline" }, "GitHub"),
            status && status.connected
              ? React.createElement(Badge, { variant: "success" }, "Connected")
              : React.createElement(Badge, { variant: "outline" }, "Not connected"),
          ),
        ),
        React.createElement(
          CardContent,
          { className: "flex flex-col gap-4" },
          React.createElement(
            "p",
            { className: "text-sm text-muted-foreground" },
            "Connect Hermes to GitHub with a fine-grained personal access token. Fine-grained tokens let you pick exactly which repositories Hermes may access, which is the safest way to grant repo-level push and automation permissions for your fork.",
          ),
          React.createElement(
            "div",
            { className: "flex flex-wrap gap-2" },
            React.createElement(Pill, null, "Recommended: fine-grained PAT"),
            React.createElement(Pill, null, "Choose exact repos on GitHub"),
            React.createElement(Pill, null, "Contents: read/write"),
            React.createElement(Pill, null, "Pull requests: optional but useful"),
          ),
          React.createElement(
            "ol",
            { className: "list-decimal pl-5 text-sm text-muted-foreground space-y-1" },
            React.createElement("li", null, "Open GitHub’s fine-grained token page and create a token for only the repos you want Hermes to access."),
            React.createElement("li", null, "Grant at least Contents: Read and write, plus Metadata: Read-only. Add Pull requests: Read and write if you want PR workflows."),
            React.createElement("li", null, "Paste the token below and save it into one of Hermes’s GitHub env vars."),
          ),
          React.createElement(
            "div",
            { className: "flex flex-wrap gap-3" },
            React.createElement(
              "a",
              {
                href: "https://github.com/settings/personal-access-tokens/new",
                target: "_blank",
                rel: "noopener noreferrer",
                className: "inline-flex",
              },
              React.createElement(Button, { variant: "outline", size: "sm" }, "Open GitHub token page"),
            ),
            React.createElement(Button, { variant: "ghost", size: "sm", onClick: refreshStatus, disabled: loading }, loading ? "Refreshing…" : "Refresh status"),
            status && status.token_source
              ? React.createElement(Button, { variant: "ghost", size: "sm", onClick: clearCurrentToken, disabled: saving }, saving ? "Working…" : "Clear current token")
              : null,
          ),
        ),
      ),
      React.createElement(
        Card,
        null,
        React.createElement(CardHeader, null, React.createElement(CardTitle, { className: "text-base" }, "GitHub token")),
        React.createElement(
          CardContent,
          { className: "grid gap-4" },
          React.createElement(
            "div",
            { className: "grid gap-2" },
            React.createElement(Label, null, "Save token into"),
            React.createElement(
              "div",
              { className: "flex flex-wrap gap-2" },
              ["GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN"].map(function (key) {
                return React.createElement(
                  Button,
                  {
                    key: key,
                    variant: tokenKey === key ? "default" : "outline",
                    size: "sm",
                    onClick: function () {
                      setTokenKey(key);
                    },
                  },
                  key,
                );
              }),
            ),
            React.createElement("p", { className: "text-xs text-muted-foreground" }, tokenHelp(tokenKey)),
          ),
          React.createElement(
            "div",
            { className: "grid gap-2" },
            React.createElement(Label, null, "GitHub token value"),
            React.createElement(Input, {
              type: "password",
              value: tokenValue,
              onChange: function (event) {
                setTokenValue(event.target.value);
              },
              placeholder: "github_pat_… or ghp_…",
            }),
          ),
          React.createElement(
            "div",
            { className: "flex items-center gap-2" },
            React.createElement(Button, { onClick: saveToken, disabled: saving || !tokenValue.trim() }, saving ? "Saving…" : "Save token"),
            message ? React.createElement("span", { className: "text-sm text-success" }, message) : null,
            error ? React.createElement("span", { className: "text-sm text-destructive" }, error) : null,
          ),
          status && status.token_source
            ? React.createElement(
                "div",
                { className: "border border-border p-3 text-sm text-muted-foreground" },
                "Current active GitHub env var: ",
                React.createElement("code", { className: "text-foreground" }, status.token_source),
                status.token_prefix ? React.createElement("span", null, " · token prefix ", React.createElement("code", { className: "text-foreground" }, status.token_prefix)) : null,
              )
            : null,
        ),
      ),
      React.createElement(
        Card,
        null,
        React.createElement(CardHeader, null, React.createElement(CardTitle, { className: "text-base" }, "GitHub access check")),
        React.createElement(
          CardContent,
          { className: "grid gap-4" },
          loading
            ? React.createElement("div", { className: "text-sm text-muted-foreground" }, "Checking GitHub connection…")
            : null,
          !loading && status && !status.connected
            ? React.createElement(
                "div",
                { className: "grid gap-2 border border-border p-4 text-sm text-muted-foreground" },
                React.createElement("div", null, "No valid GitHub repo token is connected yet."),
                status && status.error
                  ? React.createElement("div", { className: "text-destructive" }, "GitHub error: ", status.error.message)
                  : null,
              )
            : null,
          !loading && status && status.connected
            ? React.createElement(
                React.Fragment,
                null,
                React.createElement(
                  "div",
                  { className: "grid gap-2 border border-border p-4" },
                  React.createElement(
                    "div",
                    { className: "flex items-center gap-2 flex-wrap" },
                    React.createElement("span", { className: "text-sm font-medium" }, status.user && status.user.login ? status.user.login : "Connected account"),
                    status.user && status.user.name ? React.createElement(Badge, { variant: "outline" }, status.user.name) : null,
                    status.scopes && status.scopes.length
                      ? React.createElement(Badge, { variant: "outline" }, status.scopes.join(", "))
                      : React.createElement(Badge, { variant: "outline" }, "fine-grained or scope-hidden token"),
                  ),
                  status.user && status.user.html_url
                    ? React.createElement(
                        "a",
                        {
                          href: status.user.html_url,
                          target: "_blank",
                          rel: "noopener noreferrer",
                          className: "text-sm text-primary underline",
                        },
                        status.user.html_url,
                      )
                    : null,
                  React.createElement("div", { className: "text-xs text-muted-foreground" }, "GitHub API rate limit remaining: ", status.rate_limit_remaining || "unknown"),
                ),
                React.createElement(
                  "div",
                  { className: "grid gap-2 border border-border p-4" },
                  React.createElement("div", { className: "text-sm font-medium" }, "Current local repo"),
                  repo.origin_repo
                    ? React.createElement(
                        React.Fragment,
                        null,
                        React.createElement("div", { className: "text-sm text-muted-foreground" }, repo.origin_repo.full_name),
                        React.createElement("div", { className: "text-xs text-muted-foreground" }, "Branch: ", repo.branch || "unknown"),
                        currentRepoAccess
                          ? React.createElement(
                              React.Fragment,
                              null,
                              React.createElement(
                                Badge,
                                { variant: currentRepoAccess.accessible ? "success" : "destructive" },
                                currentRepoAccess.accessible ? "Token can access this repo" : "Token cannot access this repo yet",
                              ),
                              React.createElement(RepoPermissionBadges, { permissions: currentRepoAccess.permissions }),
                            )
                          : React.createElement("div", { className: "text-xs text-muted-foreground" }, "Current repo access could not be checked."),
                      )
                    : React.createElement("div", { className: "text-sm text-muted-foreground" }, "No GitHub origin remote detected."),
                ),
              )
            : null,
        ),
      ),
      React.createElement(
        Card,
        null,
        React.createElement(CardHeader, null, React.createElement(CardTitle, { className: "text-base" }, "Accessible repositories preview")),
        React.createElement(
          CardContent,
          { className: "grid gap-3" },
          status && status.repo_preview && status.repo_preview.length
            ? status.repo_preview.map(function (repoItem) {
                return React.createElement(
                  "div",
                  { key: repoItem.full_name, className: "grid gap-2 border border-border p-3" },
                  React.createElement(
                    "div",
                    { className: "flex items-center justify-between gap-3 flex-wrap" },
                    React.createElement("a", {
                      href: repoItem.html_url,
                      target: "_blank",
                      rel: "noopener noreferrer",
                      className: "font-medium text-sm text-primary underline",
                    }, repoItem.full_name),
                    React.createElement(Badge, { variant: repoItem.private ? "outline" : "success" }, repoItem.private ? "private" : "public"),
                  ),
                  React.createElement(RepoPermissionBadges, { permissions: repoItem.permissions }),
                );
              })
            : React.createElement("div", { className: "text-sm text-muted-foreground" }, "No repository preview available yet."),
        ),
      ),
      React.createElement(
        Card,
        null,
        React.createElement(CardHeader, null, React.createElement(CardTitle, { className: "text-base" }, "Model / provider logins")),
        React.createElement(
          CardContent,
          { className: "p-0" },
          React.createElement(OAuthProvidersCard, {
            onError: function (msg) {
              setError(msg);
            },
            onSuccess: function (msg) {
              setMessage(msg);
            },
          }),
        ),
      ),
    );
  }

  window.__HERMES_PLUGINS__.register("connections", ConnectionsPage);
})();
