// Secret from environment
const secret = pm.environment.get("ADMIN_SECRET_LOCAL");

// Generate timestamp + nonce
const timestamp = Math.floor(Date.now() / 1000);
const nonce = crypto.randomUUID().replace(/-/g, "");

// Build payload EXACTLY like Python
const payloadObj = {
  user: "admin",
  ts: timestamp,
  nonce: nonce,
};

// Compact JSON (same as separators=(",", ":"))
const payloadStr = JSON.stringify(payloadObj);

// Convert to WordArray (binary)
const payloadWordArray = CryptoJS.enc.Utf8.parse(payloadStr);

// Compute raw HMAC (binary)
const signature = CryptoJS.HmacSHA256(payloadWordArray, secret);

// Create binary payload + "." + binary signature
const dot = CryptoJS.enc.Utf8.parse(".");
const combined = payloadWordArray.clone().concat(dot).concat(signature);

// URL-safe Base64 encode
let token = CryptoJS.enc.Base64.stringify(combined);

// Convert to URL-safe (Python uses urlsafe_b64encode)
token = token.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

// Store token
pm.environment.set("ADMIN_TOKEN_LOCAL", token);
