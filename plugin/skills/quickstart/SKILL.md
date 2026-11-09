---
name: quickstart
description: >
  Use when someone wants to try Pontem end to end: install the pontem CLI, log in,
  enroll a Linux device over SSH, publish and install the quickstart compose package
  with its config namespace, open the running service through a browser link, then
  change a config value and watch it land on the device. Triggers: "/pontem:quickstart",
  "onboard me to Pontem", "set up Pontem on my device", "Pontem quickstart".
---

# Pontem quickstart

You walk the user from nothing to a service running on their own device, managed by
Pontem, with a browser link to it and a config change they made themselves. Every
step is idempotent: before creating something, check whether it already exists and
reuse it. If the user re-runs this skill, pick up where the last run stopped.

Talk to the user in short lines: what you are about to do, then the result. Show
commands you run only when they fail or when the user has to run one. The user doesn't
see command output, so anything they need from it, like the link in step 7, goes in
your own message.

This skill's directory holds `package/`, the four files you publish in step 5.

## Inputs

Collect these before step 1. Take them from the user's message when present.

| Input | Where it comes from |
|---|---|
| Control plane | The domain in the admin app URL: `https://<control-plane>/admin/o/<tenant>/…` |
| Tenant | The segment after `/o/` in that URL |
| SSH target | Whatever the user passes to `ssh` to reach the device: an alias, `host`, or `user@host` |
| Device name | Name shown in Pontem. Default: the device's short hostname. Lowercase letters, digits, `-` |

## Step 1: Install the CLI

```bash
command -v pontem || ls ~/.local/bin/pontem
```

If neither finds it:

```bash
curl -sSL https://storage.googleapis.com/pontem-cli-releases/install.sh | bash
```

The installer puts `pontem` in `~/.local/bin`. If that is not on `PATH` in your shell,
call it as `~/.local/bin/pontem` for the rest of this run. Confirm with `pontem version`.

## Step 2: Log in

```bash
pontem status
pontem status --url <control-plane>
```

`pontem status` shows the saved control plane, sometimes by a short environment
name like `prod` instead of its URL. With `--url` it shows the one from the inputs.
If both name the same control plane, the tenant is right, and the token is valid,
skip ahead. Otherwise:

```bash
pontem login --url <control-plane> --tenant <tenant>
```

This opens a browser. Tell the user to finish signing in there, then re-run
`pontem status` to confirm.

## Step 3: Check the device

The device must be Linux on x86_64 or ARM64 with systemd and Docker Engine. Probe it
without prompting:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 <ssh-target> '
  uname -m
  command -v systemctl >/dev/null && echo systemd=ok || echo systemd=missing
  command -v curl >/dev/null && echo curl=ok || echo curl=missing
  command -v docker >/dev/null && echo docker=ok || echo docker=missing
  sudo -n true 2>/dev/null && echo sudo=nopasswd || echo sudo=password
  (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE "[:.]8080[[:space:]]" && echo port8080=busy || echo port8080=free
  hostname -s'
```

Act on the result:

- **SSH fails with `Permission denied` or `Host key verification failed`:** the
  device wants a password, a key passphrase or a host-key confirmation, and you
  can't type one. Check whether an earlier run left a shared connection open:

  ```bash
  ssh -O check -o 'ControlPath=~/.ssh/pontem-%C' <ssh-target>
  ```

  If it isn't running, ask the user to run this in their own terminal and answer
  the prompts there. It opens a connection in the background that your `ssh` calls
  reuse, and it closes after 30 idle minutes:

  ```bash
  ssh -fN -o ControlMaster=yes -o ControlPersist=30m -o 'ControlPath=~/.ssh/pontem-%C' <ssh-target>
  ```

  Once it's open, use `-o 'ControlPath=~/.ssh/pontem-%C' <ssh-target>` as
  the SSH target for the rest of this run, including after `--` in step 4, and run
  the probe again. If their ssh can't do this (Windows OpenSSH has no
  `ControlMaster`), have them run each command that needs SSH in their own terminal,
  starting with this probe, and paste you the output.
- **SSH fails any other way** (the host doesn't resolve, the connection times out or
  is refused): ask the user for a target that `ssh <target>` reaches from this
  machine.
- **`uname -m` is not `x86_64` or `aarch64`, or systemd is missing:** stop. The
  device isn't supported.
- **curl or Docker missing:** tell the user. Offer to install Docker with Docker's
  script (`curl -fsSL https://get.docker.com | sudo sh` on the device). Run it only
  if they say yes.
- **`port8080=busy`:** pick a free port (try 8081, 8082, …) and remember it as the
  host port. You set it in step 6.
- **`sudo=password`:** you can't answer the sudo prompt from here. In step 4 the user
  runs enroll in their own terminal.

## Step 4: Enroll the device

Check whether a device with this name already exists:

```bash
pontem device list
```

If it does, ask the user whether it's this machine. If yes, skip to the end of this
step. If no, pick another name.

With `sudo=nopasswd`, enroll it yourself:

```bash
pontem device enroll --name <device-name> -- <ssh-target>
```

With `sudo=password`, ask the user to run that same command in a separate terminal,
where they can type the device's sudo password, and tell you when it finishes.

Enrollment takes about a minute. If it fails after creating the device, the CLI
prints a retry command with `--id` and `--token`. Run that instead of enrolling again.

Once enrollment succeeds, close the shared SSH connection if the user opened one in
step 3. Nothing after this needs SSH except step 7's fallback:

```bash
ssh -O exit -o 'ControlPath=~/.ssh/pontem-%C' <ssh-target>
```

Wait until the device reports in. Poll every 10 seconds, for up to 3 minutes:

```bash
pontem device describe --name <device-name>
```

Once it shows a recent report from the device, have it check in every 5 seconds
instead of the default 30, so the install and the config change land quickly:

```bash
pontem device settings set --name <device-name> --heartbeat-interval 5
```

## Step 5: Publish the quickstart package

Copy this skill's `package/` directory to `./pontem-quickstart/` in the user's
working directory, so they keep the files. Run the rest of this step from there.

1. Give the page read access to Pontem. The page shows its own device as the
   Pontem API reports it, using a service-account key that can only read
   devices. The key goes straight into a tenant secret and is never printed.

   Before creating the key, tell the user in one line that it's read-only: it can
   see devices in the tenant but can't change anything.

   Skip this if `pontem secrets list` already shows `quickstart-api-key`. In that
   case, use its `LATEST` version number in sub-step 2 instead of `1`.

   Reuse the `sa_quickstart` service account if `pontem service-account list`
   shows one. Otherwise create it; it prints the new ID (`sa_…`):

   ```bash
   pontem service-account create --name sa_quickstart \
     --description "Reads device details for the quickstart page" \
     --initial-scopes devices:read
   ```

   Issue a 30-day key and store it as the secret in one pipe. `key create` writes
   the key only to stdout, so it never appears in the output:

   ```bash
   pontem service-account key create --sa <sa-id> --name quickstart-page --expires 30d \
     | tr -d '\n' | pontem secrets create quickstart-api-key --from-file -
   ```

2. In `namespace.yaml`, set the `ADMIN_URL` default to
   `https://<control-plane>/admin/o/<tenant>`, the organization's admin URL from
   the inputs. The page links to the device there and calls the Pontem API on
   the same host. If the secret's version isn't `1`, set `API_KEY`'s
   `default.version` to match. Then create or update the namespace. Re-running is
   safe.

   ```bash
   pontem config namespace set -f namespace.yaml --yes
   ```

3. Create the package if it doesn't exist:

   ```bash
   pontem package list
   pontem package create -f package.yaml
   ```

4. Publish version `v0.2.4` if it isn't published yet:

   ```bash
   pontem package version list quickstart
   pontem package publish -f version.yaml --compose-file docker-compose.yaml --yes
   ```

## Step 6: Install it on the device

If step 3 found port 8080 busy, set the port for this device first:

```bash
pontem config override set HOST_PORT=<port> --namespace quickstart --scope device:<device-name> --yes
```

Install and wait for it to settle. The install also activates the `quickstart`
config namespace on the device.

```bash
pontem device package install quickstart --name <device-name> --latest --if-not-assigned --wait --yes
```

The first install pulls the image, which takes 30 to 90 seconds. If it ends in
anything but Healthy, run `pontem device describe --name <device-name>` and
`pontem device logs --name <device-name>`, show the user what failed, and stop.

## Step 7: Give the user a link

The link goes through Pontem's app proxy, so the device needs a connector.

```bash
pontem device connector enable --name <device-name> --yes
```

If it says the connector package or app proxy isn't available on this control plane,
tell the user their administrator has to enable app access, and skip to step 8.
Use `ssh <ssh-target> curl -s localhost:<port>/config.json` for the before and after.
If you closed a shared SSH connection in step 4, ask the user to open it again first.

Publish the port as an app. Check `pontem app list` first; reuse an existing
`quickstart` app on this device.

```bash
pontem app publish quickstart --device <device-name> --port <port> --output json
```

Keep the app ID from the output and use it as `<app>` from here on. Print the link:

```bash
pontem app url <app>
```

A new link takes about 20 seconds to come online. Until it does, `pontem curl <app> /health`
fails with HTTP 503 "API route offline". Retry it every 5 seconds, for up to 2 minutes.

Once it answers `ok`, stop and give the user the link. Write the URL itself in your
message, on its own line, and ask them to open it. Opening it asks them to sign in to
Pontem, then shows the page with the greeting "Hello World!" and a panel of their
device's details from the Pontem API. Wait until they say the page is open before
starting step 8.

If the panel shows an error instead, the message says why. The usual one is "The
Pontem API refused the key": check that `sa_quickstart` has `devices:read` with
`pontem service-account describe <sa-id>`.

## Step 8: Change a config value

Ask the user what the page should say instead of "Hello World!". Tell them to keep
the page open: it watches for the change and updates on its own.

Record the current state:

```bash
pontem curl <app> /config.json
```

Set the new value for this device only. It overrides the namespace default without
changing it for other devices:

```bash
pontem config override set GREETING='<their text>' --namespace quickstart --scope device:<device-name> --yes
```

Single quotes keep the shell from expanding `!`, `$` or backticks in their text. Write
a single quote inside it as `'\''`.

The device checks in every 5 seconds. It gets the change at its next check-in and
restarts the service with the new value soon after, so this takes about 20
seconds. Poll `pontem curl <app> /config.json` every
5 seconds until `boot_id` changes, for up to 2 minutes. Requests fail for a few
seconds while the service restarts; keep polling. If it hasn't changed by
then, run `pontem device package redeploy quickstart --name <device-name> --yes` and
poll again.

Show the user what changed, as a small before and after table of `greeting` and
`started_at`. Then explain in two or three sentences:

- The namespace default is still "Hello World!". The override applies to this
  device only.
- The daemon on the device restarted the service with the new value. Nobody
  published a new package version.
- The open page followed the device as the Pontem API reports it: amber as soon
  as the change was saved, green once Pontem had the device back in sync. Its
  activity log has a line for each change in between.

## Wrap up

Tell the user what they now have, in one short list: the enrolled device, the
`quickstart` package and version, the `quickstart` config namespace and their
device override, the `sa_quickstart` service account and its 30-day key, and the
app link. Point them at `./pontem-quickstart/` for the
files.

Offer these next steps without running them:

- Go back to the default 30-second check-ins, for a device on a metered link or
  once the trial is over:
  `pontem device settings set --name <device-name> --heartbeat-interval 30`
- Revert the greeting:
  `pontem config override delete --namespace quickstart --scope device:<device-name> --key GREETING`
- Remove the quickstart from the device:
  `pontem app remove <app>` and `pontem device package remove quickstart --name <device-name>`
- Revoke the page's key: find its ID with `pontem service-account key list --sa <sa-id>`,
  then `pontem service-account key revoke <key-id> --sa <sa-id>`. The page's
  device panel stops working; the rest of the page keeps running.
- Renew the key before it expires in 30 days: issue a new one and publish it as
  a new version of the secret, then point `API_KEY` at that version.
  `pontem service-account key create --sa <sa-id> --name quickstart-page --expires 30d | tr -d '\n' | pontem secrets publish quickstart-api-key --from-file -`
