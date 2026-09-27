package com.quantumflex.cockpit;

import android.content.Intent;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.cert.Certificate;
import java.security.spec.ECGenParameterSpec;

/**
 * QuantumFlex operator key, held in the Pixel's StrongBox secure element.
 *
 * The private key is generated inside StrongBox, is non-exportable, and is usable
 * only while the device is unlocked. The server pins its public key at enrollment
 * (scripts/enroll_pixel_key.py, over USB) after checking the key attestation chain,
 * then accepts control requests only when signed by this key.
 *
 * Enrollment is triggered over ADB, never from the network:
 *   am start -n com.quantumflex.cockpit/.MainActivity --es qf_enroll_challenge <hex>
 * which writes files/qf_enroll.json for the host to pull with run-as.
 */
@CapacitorPlugin(name = "QFDeviceKey")
public class QFDeviceKeyPlugin extends Plugin {
    static final String ALIAS = "qf-operator-key";
    static final String DEVICE_ID = "pixel-11-pro";
    static final String ENROLL_EXTRA = "qf_enroll_challenge";
    static final String ENROLL_FILE = "qf_enroll.json";

    @Override
    public void load() {
        handleEnrollIntent(getActivity().getIntent());
    }

    @Override
    protected void handleOnNewIntent(Intent intent) {
        super.handleOnNewIntent(intent);
        handleEnrollIntent(intent);
    }

    @PluginMethod
    public void sign(PluginCall call) {
        String message = call.getString("message");
        if (message == null) {
            call.reject("message is required");
            return;
        }
        try {
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            PrivateKey key = (PrivateKey) ks.getKey(ALIAS, null);
            if (key == null) {
                call.reject("operator key not enrolled");
                return;
            }
            Signature s = Signature.getInstance("SHA256withECDSA");
            s.initSign(key);
            s.update(message.getBytes(StandardCharsets.UTF_8));
            JSObject ret = new JSObject();
            ret.put("deviceId", DEVICE_ID);
            ret.put("signature", Base64.encodeToString(s.sign(), Base64.NO_WRAP));
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("signing failed: " + e.getMessage());
        }
    }

    private void handleEnrollIntent(Intent intent) {
        if (intent == null) return;
        String challengeHex = intent.getStringExtra(ENROLL_EXTRA);
        if (challengeHex == null) return;
        intent.removeExtra(ENROLL_EXTRA);
        File out = new File(getContext().getFilesDir(), ENROLL_FILE);
        JSONObject result = new JSONObject();
        try {
            byte[] challenge = hexToBytes(challengeHex);
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            ks.deleteEntry(ALIAS);

            KeyPairGenerator kpg = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore");
            kpg.initialize(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
                    .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setIsStrongBoxBacked(true)
                    .setUnlockedDeviceRequired(true)
                    .setAttestationChallenge(challenge)
                    .build());
            kpg.generateKeyPair();

            JSONArray chain = new JSONArray();
            for (Certificate c : ks.getCertificateChain(ALIAS)) {
                chain.put(Base64.encodeToString(c.getEncoded(), Base64.NO_WRAP));
            }
            result.put("deviceId", DEVICE_ID);
            result.put("attestationChain", chain);
        } catch (Exception e) {
            try { result.put("error", e.getClass().getSimpleName() + ": " + e.getMessage()); } catch (Exception ignored) {}
        }
        try (FileOutputStream fos = new FileOutputStream(out)) {
            fos.write(result.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    private static byte[] hexToBytes(String hex) {
        if (hex.length() % 2 != 0 || hex.length() < 32 || hex.length() > 256) {
            throw new IllegalArgumentException("challenge must be 16-128 bytes of hex");
        }
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }
}
