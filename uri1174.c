#include <stdio.h>
int Impressao (int i, float x) {
    printf("x = %.1f\n", x);
    printf("A[%d] = %.1f\n", i, x);

    return 1;
}


int main() {
	float A[5];
	int i, x;

	for (i=0; i<5; i++)
		scanf("%f", &A[i]);

    for (i=0; i<5; i++) {
        if (A[i] <= 10.0) {
            x = Impressao(i, A[i]);

        }
    }


	return 0;

}
