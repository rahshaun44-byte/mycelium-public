CC = clang
CFLAGS = -O2 -target bpf -Wall

all: qf_ingress.o

qf_ingress.o: qf_ingress.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f qf_ingress.o

.PHONY: all clean
