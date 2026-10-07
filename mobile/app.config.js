const path = require('path');
const dotenv = require('dotenv');

dotenv.config({ path: path.resolve(__dirname, '.env') });
dotenv.config({ path: path.resolve(__dirname, '..', '.env') });

module.exports = ({ config }) => ({
  ...config,
  extra: {
    ...config.extra,
    apiUrl: process.env.LEERAL_API_URL ?? '',
    supportWhatsApp: process.env.LEERAL_SUPPORT_WHATSAPP ?? '15556389708',
  },
});
