// Telegram user (Mini App safe)
const tg = window.Telegram.WebApp;
tg.ready();

const user = tg.initDataUnsafe.user;
const telegram_id = String(user.id);
const username = user.username || "anonymous";

const pointsEl = document.getElementById("points");
const countdownEl = document.getElementById("countdown");
const claimBtn = document.getElementById("claimBtn");

let countdownInterval = null;

// Convert seconds → HH:MM:SS
function formatTime(seconds) {
  const h = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

// Start countdown timer
function startCountdown(seconds) {
  clearInterval(countdownInterval);
  countdownEl.textContent = formatTime(seconds);

  countdownInterval = setInterval(() => {
    seconds--;
    countdownEl.textContent = formatTime(seconds);

    if (seconds <= 0) {
      clearInterval(countdownInterval);
      claimBtn.disabled = false;
      claimBtn.textContent = "Claim Daily Reward";
    }
  }, 1000);
}

// Load dashboard data
async function loadDashboard() {
  const res = await fetch("/api/dashboard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ telegram_id, username })
  });

  const data = await res.json();

  pointsEl.textContent = data.points;

  if (data.can_claim) {
    countdownEl.textContent = "Available now";
    claimBtn.disabled = false;
  } else {
    claimBtn.disabled = true;
    startCountdown(data.remaining);
  }
}

// Claim reward
claimBtn?.addEventListener("click", async () => {
  claimBtn.disabled = true;
  claimBtn.textContent = "Claiming...";

  const res = await fetch("/api/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ telegram_id })
  });

  if (res.ok) {
    loadDashboard();
  } else {
    alert("Too early to claim");
    loadDashboard();
  }
});

// Init
if (pointsEl && claimBtn && countdownEl) {
  loadDashboard();
}
// ======================
// REFERRALS LOGIC
// ======================

async function loadReferrals() {
  const res = await fetch("/api/referrals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ telegram_id })
  });

  const data = await res.json();

  // Update stats
  document.getElementById("refCount").textContent = data.total_referrals;
  document.getElementById("refPoints").textContent = data.earned_points;

  // Referral list
  const list = document.getElementById("refList");
  list.innerHTML = "";

  if (data.usernames.length === 0) {
    list.innerHTML = "<li>No referrals yet</li>";
  } else {
    data.usernames.forEach(username => {
      const li = document.createElement("li");
      li.textContent = "@" + username;
      list.appendChild(li);
    });
  }

  // Referral link
  document.getElementById("refLink").value =
    `https://t.me/pulsex_airdrop_bot?start=${telegram_id}`;
}

// Copy referral link
function copyRef() {
  const input = document.getElementById("refLink");
  input.select();
  document.execCommand("copy");
  alert("Referral link copied!");
}

// Auto-load on referrals page
if (document.getElementById("refCount")) {
  loadReferrals();
}
// ======================
// WALLET LOGIC
// ======================

async function loadWallet() {
  const res = await fetch("/api/get_wallet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ telegram_id })
  });

  const data = await res.json();

  if (data.wallet_address) {
    document.getElementById("walletInput").value = data.wallet_address;
  }
}

async function saveWallet() {
  const wallet = document.getElementById("walletInput").value.trim();

  if (!wallet) {
    alert("Please enter a wallet address");
    return;
  }

  await fetch("/api/save_wallet", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      telegram_id,
      wallet_address: wallet
    })
  });

  alert("Wallet saved successfully");
}

// Auto-load wallet page
if (document.getElementById("walletInput")) {
  loadWallet();
}
