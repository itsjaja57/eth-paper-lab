# ETH Paper Lab — free background prototype

Two independent ETH/GBP paper accounts, £1,000 each. No exchange keys, no real orders.

## Setup (Android or desktop)
1. Create a **public** GitHub repository (for example `eth-paper-lab`). Public means anyone can view your simulated trade history. Do not put secrets in the repository.
2. Upload **all files and folders** from this package, including `.github/workflows/paper.yml`. The easiest method is to unzip on a computer and upload via GitHub, or use GitHub's web file creator for the workflow path.
3. In repository **Settings → Actions → General**, ensure Actions are enabled and workflow permissions allow **Read and write permissions** (if that option is available). Repository/org policies may restrict this.
4. Go to **Actions → Update ETH paper accounts → Run workflow** to perform the first update. Check the run logs for errors.
5. In **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/docs`, and save. Open the Pages URL GitHub provides.
6. Refresh the dashboard to see the latest snapshot. The workflow is scheduled every 5 minutes, but GitHub can delay or skip runs; Pages publishing may add delay.

## Limitations
- GitHub Actions schedules are best-effort, not guaranteed continuous. Some schedules may be disabled after 60 days of inactivity on public repositories. Check the Actions tab if updates stop.
- Coinbase candles can be sparse; the script intentionally skips uncertain intervals instead of inventing trades.
- A five-minute check and five-minute candle strategy are **not** live execution. No intra-candle stop orders, slippage, or spread model. Fees are illustrative.
- A market fetch failure leaves positions and trade history unchanged, but records the error. The last available price may be stale.
- Public repository makes the simulated results public. A private repository may consume free Actions minutes and requires compatible Pages availability.
- Existing v3/v4 browser localStorage history **does not automatically migrate**. New cloud accounts begin at £1,000 each.
- To reset an account, edit `docs/state.json` using the initial values in the package; this erases its paper history.
