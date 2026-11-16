# Development and deployment boundaries

Read docs/environments.md before changing launch/deployment configuration.
Keep one shared source line on main; local and server profiles are execution
environments, not separate copies of the authoring/design workflow.

When runner/deployment.local.json identifies this checkout as local:
- Use its own .venv, website/.dev.vars, runner/settings.local.json and runtime.
- Use the loopback development site and its simulated users/data only.
- Do not copy a production worker token or alter the older Mac bridge checkout.
- Do not start/update the server, deploy the site or migrate hosted databases as
  a side effect of local tests. Existing user authorization still governs actions.

Private settings, keys, runtime receipts, model logs and user artifacts remain
untracked. Report the source revision, actual environment and validation scope;
configuration validation does not prove an online worker or successful generation.
