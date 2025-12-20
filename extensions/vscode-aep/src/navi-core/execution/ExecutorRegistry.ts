import { Executor } from './Executor';

export class ExecutorRegistry {
    private registry: Map<string, Executor>;

    constructor(entries: Array<[string, Executor]> = []) {
        this.registry = new Map(entries);
    }

    get(name: string): Executor {
        const exec = this.registry.get(name);
        if (!exec) throw new Error(`Executor not found: ${name}`);
        return exec;
    }
}
