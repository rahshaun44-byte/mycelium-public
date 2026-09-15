#include <linux/bpf.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>

#define QFXK_MAGIC 0x5146584B
#define QFX_INGRESS_PORT 9443 // Port guard to protect Tailscale DNS (53) & mesh control

SEC("xdp")
int qf_pre_ingress(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;

    // Tailscale TUN packets start at Layer 3 (IP header)
    struct iphdr *iph = data;
    if ((void *)(iph + 1) > data_end)
        return XDP_PASS; // Packet too small, let kernel handle

    // Target UDP payloads
    if (iph->protocol != IPPROTO_UDP)
        return XDP_PASS; 

    struct udphdr *udph = (void *)iph + (iph->ihl * 4);
    if ((void *)(udph + 1) > data_end)
        return XDP_PASS;

    // Port Guard: Only evaluate packets destined for QuantumFlex Ingress
    // Pass Tailscale DNS (53), WireGuard disco/keepalives, and mesh traffic unharmed
    if (udph->dest != __builtin_bswap16(QFX_INGRESS_PORT))
        return XDP_PASS;

    // Inspect the first 4 bytes of the UDP payload for the PQC Magic Header
    unsigned int *payload_magic = (void *)(udph + 1);
    if ((void *)(payload_magic + 1) > data_end)
        return XDP_DROP; // Malformed/empty payload

    // Validate Magic (assuming network byte order / Big Endian)
    if (*payload_magic != __builtin_bswap32(QFXK_MAGIC)) {
        // SHUNT: Instantly drop non-QuantumFlex packets with 0 OS allocation
        return XDP_DROP; 
    }

    // VALID: Pass the pristine packet up to the Wasm Gatekeeper
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
