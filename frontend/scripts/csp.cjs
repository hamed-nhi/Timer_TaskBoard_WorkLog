/* Authorize only the inline scripts emitted by this static Next.js build. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hashes = new Set();
function walk(dir) {
  for (const entry of fs.readdirSync(dir, {withFileTypes:true})) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (entry.name.endsWith('.html')) {
      const html = fs.readFileSync(file, 'utf8');
      for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
        if (!/\bsrc\s*=/i.test(match[1])) hashes.add("'sha256-" + crypto.createHash('sha256').update(match[2]).digest('base64') + "'");
      }
    }
  }
}
walk(path.join(process.cwd(), 'out'));
if (!hashes.size) throw Error('No exported inline scripts found; check the Next export format');
const policy = ["default-src 'self'", "script-src 'self' " + [...hashes].sort().join(' '), "style-src 'self' 'unsafe-inline'", "img-src 'self' data:", "font-src 'self'", "connect-src 'self'", "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"].join('; ');
fs.writeFileSync('security-headers.caddy', 'Content-Security-Policy "' + policy + '"\n');
console.log('CSP generated for ' + hashes.size + ' static inline scripts (' + policy.length + ' bytes)');
