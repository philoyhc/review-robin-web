**Update docs/cli_setup.md A2.1 to say that the below is not a real "error""**

The distribution is already the requested version.
Error code: Wsl/Service/WSL_E_VM_MODE_INVALID_STATE

**Run this first:**

wsl --update

**Then:**

wsl

Create account, password, etc


**After A.5, clone repo first then check:**

mkdir -p ~/src && cd ~/src
gh repo clone philoyhc/review-robin-web
cd review-robin-web
git config --global user.name "Loy Hui Chieh"
git config --global user.email "<same noreply address as machine one>"
git commit --allow-empty -m "identity test" && git reset --hard HEAD~1


**Before B.5, log into azure first**

az login

**If failed, follow instructions, e.g.,**

az login --tenant 8b73f1e7-bf3d-4fb3-8b00-d6248745ae62

**Before B.9.4:**

PG_SERVER=$(az postgres flexible-server list -g rg-review-robin-web-dev --query "[0].name" -o tsv)
echo "PG_SERVER='${PG_SERVER}'"

az postgres flexible-server show \
    -g rg-review-robin-web-dev --name "${PG_SERVER}" \
    --query "{name:name, state:state, network:network}" -o jsonc

MY_IP=$(curl -sS https://checkip.amazonaws.com || curl -sS https://ifconfig.me || curl -sS https://icanhazip.com)
MY_IP=$(echo "$MY_IP" | tr -d '[:space:]')
echo "MY_IP='${MY_IP}'"

