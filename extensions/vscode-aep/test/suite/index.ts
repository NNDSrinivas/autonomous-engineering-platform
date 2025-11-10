import * as path from 'path';
import Mocha from 'mocha';
import { glob } from 'glob';

export function run(): Promise<void> {
    const mocha = new Mocha({ ui: 'bdd', color: true, timeout: 20000 });
    const testsRoot = path.resolve(__dirname);

    return new Promise((resolve, reject) => {
        glob('**/*.test.js', { cwd: testsRoot }).then((files: string[]) => {
            try {
                for (const f of files) {
                    mocha.addFile(path.resolve(testsRoot, f));
                }
                mocha.run((failures: number) => {
                    if (failures > 0) {
                        reject(new Error(`${failures} tests failed.`));
                    } else {
                        resolve();
                    }
                });
            } catch (e) {
                reject(e);
            }
        }).catch(reject);
    });
}
